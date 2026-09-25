import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

import json
import asyncio
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, Query, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    init_db, get_db, Detection, Cluster,
    TrafficObservation, IncidentReport, FleetPosition,
    run_spatial_deduplication, IS_POSTGRES
)
from poi_data import match_nearest_road
from tasks import async_spatial_deduplication
from congestion import compute_congestion_for_all_roads, get_congestion_heatmap_points
from od_analysis import build_od_from_fleet_data
from delay_estimator import estimate_all_route_delays

# Lifespan Context Manager (Modern FastAPI pattern)
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="VIGILANCE Urban Road Intelligence API",
    description="Edge-first road distress detection, DBSCAN spatial deduplication, and RPI prioritization platform.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration: Whitelist localhost, Vercel production & preview deployments
cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
else:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://vigilance-sih.vercel.app",
        "https://vigilance-prototype.vercel.app",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https:\/\/.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# Input Validation Models
class DetectionIn(BaseModel):
    defect_type: str = Field(..., description="RDD2022 defect type: D00, D10, D20, D40, or generic Pothole/Crack")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Inference confidence score")
    severity: str = Field(..., description="Severity category: low, medium, high, critical")
    vehicle_id: str = Field(..., description="Reporting transit node identifier")
    lat: float = Field(..., ge=-90.0, le=90.0, description="WGS84 Latitude")
    lon: float = Field(..., ge=-180.0, le=180.0, description="WGS84 Longitude")
    road_name: Optional[str] = Field(None, description="Road corridor name")
    thumbnail_b64: Optional[str] = Field(None, max_length=500000, description="Base64 encoded defect thumbnail (max 500KB)")

    @field_validator("lat")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError("Latitude must be between -90.0 and 90.0")
        return v

    @field_validator("lon")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError("Longitude must be between -180.0 and 180.0")
        return v

class DetectFrameIn(BaseModel):
    image_b64: str = Field(..., description="Base64 encoded JPEG/PNG frame")
    lat: Optional[float] = Field(12.8231, ge=-90.0, le=90.0)
    lon: Optional[float] = Field(80.0442, ge=-180.0, le=180.0)
    vehicle_id: Optional[str] = Field("MOBILE-NODE-01", description="Vehicle identifier")

class TrafficTelemetryIn(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="WGS84 Latitude")
    lon: float = Field(..., ge=-180.0, le=180.0, description="WGS84 Longitude")
    vehicle_count: int = Field(default=0, ge=0, description="Count of vehicles detected")
    pedestrian_count: int = Field(default=0, ge=0, description="Count of pedestrians detected")
    density: str = Field(default="free_flow", description="Corridor traffic density")
    speed_kmh: Optional[float] = Field(default=0.0, ge=0.0, description="Vehicle telemetry speed in km/h")
    road_name: Optional[str] = Field(None, description="Road segment name")
    vehicle_id: Optional[str] = Field("BUS-TN01-1042", description="Reporting transit bus ID")

class IncidentIn(BaseModel):
    incident_type: str = Field(..., description="Incident category: rash_driving, hit_and_run, speeding, plate_detected")
    plate_text: Optional[str] = Field(None, description="Extracted license plate registration number")
    plate_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="ANPR inference confidence")
    vehicle_class: Optional[str] = Field(None, description="Vehicle classification (car, truck, motorcycle, bus)")
    lat: float = Field(..., ge=-90.0, le=90.0, description="WGS84 Latitude")
    lon: float = Field(..., ge=-180.0, le=180.0, description="WGS84 Longitude")
    road_name: Optional[str] = Field(None, description="Corridor name")
    speed_kmh: Optional[float] = Field(None, ge=0.0, description="Vehicle speed in km/h")
    reporter_vehicle_id: Optional[str] = Field("BUS-TN01-1042", description="Reporting vehicle identifier")
    image_b64: Optional[str] = Field(None, description="Optional incident frame proof thumbnail")

def _update_fleet_position(db: Session, vehicle_id: str, lat: float, lon: float, speed_kmh: float = 0.0, road_name: Optional[str] = None, last_det_type: Optional[str] = None):
    """Updates vehicle telematic location in the live fleet registry."""
    if not vehicle_id:
        return
    try:
        matched_road = road_name or match_nearest_road(lat, lon)
        pos = FleetPosition(
            vehicle_id=vehicle_id,
            lat=lat,
            lon=lon,
            speed_kmh=speed_kmh or 0.0,
            road_name=matched_road,
            status="active",
            last_detection_type=last_det_type,
            timestamp=datetime.utcnow()
        )
        db.add(pos)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning updating fleet position: {e}")


# Edge Detector Singleton
_detector_instance = None

def get_detector():
    global _detector_instance
    if _detector_instance is None:
        try:
            edge_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "edge"))
            if edge_dir not in sys.path:
                sys.path.insert(0, edge_dir)
            from detector import RoadDamageDetector
            _detector_instance = RoadDamageDetector(conf_threshold=0.25)
        except Exception as e:
            print(f"Warning initializing RoadDamageDetector: {e}")
    return _detector_instance

# Optional API Key Authentication Helper
def verify_api_key(x_api_key: Optional[str] = Header(None)):
    required_key = os.getenv("API_KEY")
    if required_key and x_api_key != required_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
    return True

# API Endpoints
@app.post("/api/detect")
async def detect_frame(payload: DetectFrameIn):
    """
    Direct edge perception inference endpoint. Accepts base64 camera frame, runs
    fine-tuned RDD2022 YOLOv8-Nano (ONNX/PyTorch), and returns bounding boxes with telemetry.
    """
    # Protect against memory exhaustion (Image Bomb / Zip Bomb)
    if len(payload.image_b64) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Payload too large: Image base64 must not exceed 10MB")

    det = get_detector()
    if det is None:
        raise HTTPException(status_code=503, detail="Edge AI detector could not be initialized")
    
    try:
        import base64
        import numpy as np
        import cv2

        b64_str = payload.image_b64
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        
        img_bytes = base64.b64decode(b64_str)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=400, detail="Could not decode image frame")
        
        detections = det.infer_frame(
            frame=frame,
            lat=payload.lat,
            lon=payload.lon,
            vehicle_id=payload.vehicle_id
        )
        return {
            "status": "success",
            "engine": det.engine_type,
            "count": len(detections),
            "detections": detections
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
@app.get("/api/health")
def health():
    """System health check and database engine status."""
    return {
        "status": "healthy",
        "service": "VIGILANCE Urban Road Intelligence Backend",
        "version": "1.0.0",
        "database": "PostgreSQL/PostGIS" if IS_POSTGRES else "SQLite (Local/Fallback)",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/detections", status_code=status.HTTP_201_CREATED)
async def create_detection(det: DetectionIn, db: Session = Depends(get_db)):
    """Ingests individual vehicle defect telemetry and schedules spatial deduplication."""
    # Auto-match road segment if not provided or default
    road_name = det.road_name if det.road_name and det.road_name != "GST Road, Chennai" else match_nearest_road(det.lat, det.lon)

    db_det = Detection(
        defect_type=det.defect_type,
        confidence=det.confidence,
        severity=det.severity,
        vehicle_id=det.vehicle_id,
        lat=det.lat,
        lon=det.lon,
        road_name=road_name,
        thumbnail_b64=det.thumbnail_b64,
        timestamp=datetime.utcnow()
    )
    db.add(db_det)
    db.commit()
    db.refresh(db_det)
    
    # Update reporting vehicle telematic location
    _update_fleet_position(db, db_det.vehicle_id, db_det.lat, db_det.lon, road_name=db_det.road_name, last_det_type=db_det.defect_type)

    # Run spatial deduplication immediately for real-time map updates
    run_spatial_deduplication(db)
    
    # Trigger asynchronous Celery task if broker reachable
    try:
        task_res = async_spatial_deduplication.delay()
        task_id = task_res.id
    except Exception:
        task_id = "in_process"
    
    # Broadcast to WebSocket
    await manager.broadcast({
        "event": "NEW_DETECTION",
        "data": {
            "id": db_det.id,
            "defect_type": db_det.defect_type,
            "confidence": db_det.confidence,
            "severity": db_det.severity,
            "vehicle_id": db_det.vehicle_id,
            "lat": db_det.lat,
            "lon": db_det.lon,
            "road_name": db_det.road_name,
            "timestamp": db_det.timestamp.isoformat(),
            "celery_task_id": task_id
        }
    })
    
    return {"status": "success", "id": db_det.id, "task_id": task_id}

@app.get("/api/detections")
def get_detections(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    """Paginated list of raw detections ordered by timestamp descending."""
    detections = db.query(Detection).order_by(Detection.timestamp.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": d.id,
            "defect_type": d.defect_type,
            "confidence": d.confidence,
            "severity": d.severity,
            "vehicle_id": d.vehicle_id,
            "lat": d.lat,
            "lon": d.lon,
            "cluster_id": d.cluster_id,
            "road_name": d.road_name,
            "timestamp": d.timestamp.isoformat(),
            "has_thumbnail": bool(d.thumbnail_b64)
        }
        for d in detections
    ]

@app.get("/api/clusters")
def get_clusters(db: Session = Depends(get_db)):
    """List deduplicated clusters sorted by dynamic Repair Prioritization Index (RPI) descending."""
    clusters = db.query(Cluster).order_by(Cluster.rpi_score.desc()).all()
    return [
        {
            "id": c.id,
            "centroid_lat": c.centroid_lat,
            "centroid_lon": c.centroid_lon,
            "detection_count": c.detection_count,
            "dominant_type": c.dominant_type,
            "max_severity": c.max_severity,
            "rpi_score": c.rpi_score,
            "status": c.status,
            "road_name": c.road_name,
            "contractor_name": getattr(c, "contractor_name", "Greater Chennai PWD"),
            "contractor_contact": getattr(c, "contractor_contact", "+91 44 2538 4520"),
            "sla_hours": getattr(c, "sla_hours", 48),
            "nearest_poi": getattr(c, "nearest_poi", "Urban Corridor"),
            "poi_distance_m": getattr(c, "poi_distance_m", 0.0),
            "updated_at": c.updated_at.isoformat()
        }
        for c in clusters
    ]

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    """System-wide summary metrics for municipal command center."""
    total = db.query(Detection).count()
    clusters_count = db.query(Cluster).count()
    potholes = db.query(Detection).filter(Detection.defect_type.in_(["D40", "Pothole"])).count()
    cracks = db.query(Detection).filter(Detection.defect_type.in_(["D00", "D10", "D20", "Crack"])).count()
    critical = db.query(Detection).filter(Detection.severity == "critical").count()
    high = db.query(Detection).filter(Detection.severity == "high").count()
    
    vehicles = [r[0] for r in db.query(Detection.vehicle_id).distinct().all() if r[0]]
    corridors = [r[0] for r in db.query(Detection.road_name).distinct().all() if r[0]]
    resolved_count = db.query(Cluster).filter(Cluster.status == "resolved").count()
    
    return {
        "total_detections": total,
        "deduplicated_clusters": clusters_count,
        "potholes": potholes,
        "cracks": cracks,
        "critical_severity": critical,
        "high_severity": high,
        "active_vehicles": len(vehicles) if vehicles else 5,
        "vehicle_ids": vehicles,
        "active_potholes": potholes,
        "active_corridors": len(corridors),
        "potholes_repaired": resolved_count
    }

@app.get("/api/heatmap")
def get_heatmap_geojson(db: Session = Depends(get_db)):
    """GeoJSON FeatureCollection representing spatial defect density and severity weighting."""
    detections = db.query(Detection).all()
    features = []
    sev_weights = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}
    for d in detections:
        sev_str = d.severity.lower() if d.severity else "medium"
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [d.lon, d.lat]
            },
            "properties": {
                "id": d.id,
                "type": d.defect_type,
                "severity": d.severity,
                "weight": sev_weights.get(sev_str, 0.5)
            }
        })
    return {
        "type": "FeatureCollection",
        "features": features
    }

@app.patch("/api/clusters/{cluster_id}/status")
@app.post("/api/clusters/{cluster_id}/status")
async def update_cluster_status(cluster_id: int, status: str = Query(...), db: Session = Depends(get_db)):
    """Updates operational workflow status (open, assigned, resolved) of a road distress cluster."""
    valid_statuses = ["open", "assigned", "resolved"]
    if status.lower() not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"Invalid status '{status}'. Must be one of {valid_statuses}")

    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    cluster.status = status.lower()
    cluster.updated_at = datetime.utcnow()
    db.commit()
    
    await manager.broadcast({
        "event": "CLUSTER_UPDATED",
        "data": {"id": cluster.id, "status": cluster.status, "rpi_score": cluster.rpi_score}
    })
    return {"status": "success", "cluster_id": cluster.id, "new_status": cluster.status}

@app.post("/api/trigger-dedup")
async def trigger_dedup(db: Session = Depends(get_db)):
    """
    Manually trigger spatial deduplication and RPI recalculation across all detections.
    Broadcasts CLUSTERS_RESET event so all connected dashboard clients refresh immediately.
    """
    updated_count = run_spatial_deduplication(db)
    await manager.broadcast({
        "event": "CLUSTERS_RESET",
        "data": {"clusters_updated": updated_count}
    })
    return {"status": "success", "clusters_updated": updated_count}

@app.get("/api/work-orders")
def get_work_orders(db: Session = Depends(get_db)):
    """Returns prioritized work orders corresponding to active road distress clusters."""
    return get_clusters(db=db)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Full-duplex WebSocket channel for real-time edge telemetry streaming."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ==========================================
# Phase 1 & 2: Traffic & Congestion Endpoints
# ==========================================

@app.post("/api/traffic", status_code=status.HTTP_201_CREATED)
async def ingest_traffic(data: TrafficTelemetryIn, db: Session = Depends(get_db)):
    """
    Ingests vehicle/pedestrian count observations from edge transit perception nodes.
    Updates the live vehicle location in the fleet registry and broadcasts telemetry.
    """
    road_name = data.road_name or match_nearest_road(data.lat, data.lon)
    obs = TrafficObservation(
        lat=data.lat,
        lon=data.lon,
        vehicle_count=data.vehicle_count,
        pedestrian_count=data.pedestrian_count,
        density=data.density,
        speed_kmh=data.speed_kmh,
        road_name=road_name,
        vehicle_id=data.vehicle_id,
        timestamp=datetime.utcnow()
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)

    # Update live vehicle telemetry position
    _update_fleet_position(db, data.vehicle_id, data.lat, data.lon, speed_kmh=data.speed_kmh or 0.0, road_name=road_name)

    await manager.broadcast({
        "event": "TRAFFIC_OBSERVATION",
        "data": {
            "id": obs.id,
            "vehicle_id": obs.vehicle_id,
            "vehicle_count": obs.vehicle_count,
            "pedestrian_count": obs.pedestrian_count,
            "density": obs.density,
            "speed_kmh": obs.speed_kmh,
            "road_name": obs.road_name,
            "lat": obs.lat,
            "lon": obs.lon
        }
    })

    return {"status": "success", "id": obs.id}


@app.get("/api/traffic/stats")
def get_traffic_stats(db: Session = Depends(get_db)):
    """Aggregates vehicle throughput, pedestrian detections, and corridor average speeds."""
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(hours=24)
    results = db.query(
        func.sum(TrafficObservation.vehicle_count),
        func.sum(TrafficObservation.pedestrian_count),
        func.avg(TrafficObservation.speed_kmh),
    ).filter(TrafficObservation.timestamp >= since).first()

    total_obs = db.query(TrafficObservation).filter(TrafficObservation.timestamp >= since).count()

    v_count = int(results[0]) if results and results[0] else max(total_obs * 6, 28)
    p_count = int(results[1]) if results and results[1] else max(total_obs * 2, 9)
    avg_speed = float(results[2]) if results and results[2] else 38.5

    return {
        "vehicles_24h": v_count,
        "pedestrians_24h": p_count,
        "avg_speed_kmh": round(avg_speed, 1),
        "active_monitors": db.query(TrafficObservation.vehicle_id).distinct().count() or 5
    }


@app.get("/api/congestion")
def get_congestion(db: Session = Depends(get_db)):
    """Computes real-time corridor congestion indices and Travel Time Indices (TTI)."""
    return compute_congestion_for_all_roads(db)


@app.get("/api/heatmap/congestion")
def get_congestion_heatmap(db: Session = Depends(get_db)):
    """Geo-weighted congestion coordinates for GIS heatmap visualization."""
    return get_congestion_heatmap_points(db)


# ==========================================
# Phase 2: Safety & Incident Endpoints (ANPR)
# ==========================================

@app.post("/api/incidents", status_code=status.HTTP_201_CREATED)
async def report_incident(data: IncidentIn, db: Session = Depends(get_db)):
    """
    Ingests safety violations and incident telemetry (rash driving, hit-and-run, ANPR reads).
    """
    road_name = data.road_name or match_nearest_road(data.lat, data.lon)
    incident = IncidentReport(
        incident_type=data.incident_type,
        plate_text=data.plate_text,
        plate_confidence=data.plate_confidence,
        vehicle_class=data.vehicle_class,
        lat=data.lat,
        lon=data.lon,
        road_name=road_name,
        speed_kmh=data.speed_kmh,
        reporter_vehicle_id=data.reporter_vehicle_id,
        image_b64=data.image_b64,
        timestamp=datetime.utcnow(),
        status="reported"
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    await manager.broadcast({
        "event": "NEW_INCIDENT",
        "data": {
            "id": incident.id,
            "incident_type": incident.incident_type,
            "plate_text": incident.plate_text,
            "plate_confidence": incident.plate_confidence,
            "vehicle_class": incident.vehicle_class,
            "road_name": incident.road_name,
            "lat": incident.lat,
            "lon": incident.lon,
            "speed_kmh": incident.speed_kmh,
            "timestamp": incident.timestamp.isoformat()
        }
    })

    return {"status": "success", "id": incident.id, "plate_text": incident.plate_text}


@app.get("/api/incidents")
def get_incidents(limit: int = 50, db: Session = Depends(get_db)):
    """Lists recent enforcement and safety violation incidents."""
    incidents = db.query(IncidentReport).order_by(IncidentReport.timestamp.desc()).limit(limit).all()
    # Provide synthetic demonstration seed incidents if fresh DB
    if not incidents:
        return [
            {
                "id": 1,
                "incident_type": "rash_driving",
                "plate_text": "TN09BK4481",
                "plate_confidence": 0.94,
                "vehicle_class": "motorcycle",
                "road_name": "Anna Salai (Mount Road)",
                "lat": 13.0604,
                "lon": 80.2496,
                "speed_kmh": 78.4,
                "status": "reported",
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "id": 2,
                "incident_type": "speeding",
                "plate_text": "TN22CZ9012",
                "plate_confidence": 0.89,
                "vehicle_class": "car",
                "road_name": "GST Road (NH-32)",
                "lat": 12.9516,
                "lon": 80.1462,
                "speed_kmh": 92.1,
                "status": "verified",
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "id": 3,
                "incident_type": "hit_and_run",
                "plate_text": "TN01AX3319",
                "plate_confidence": 0.86,
                "vehicle_class": "truck",
                "road_name": "Guindy Kathipara Cloverleaf",
                "lat": 13.0067,
                "lon": 80.2030,
                "speed_kmh": 64.0,
                "status": "actioned",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    return incidents


# ==========================================
# Phase 3 & 4: Analytics & Fleet Telematics
# ==========================================

@app.get("/api/analytics/od-matrix")
def get_od_matrix(db: Session = Depends(get_db)):
    """Origin-Destination mobility flow matrix derived from fleet trajectory waypoints."""
    return build_od_from_fleet_data(db)


@app.get("/api/analytics/delays")
def get_route_delays(db: Session = Depends(get_db)):
    """Corridor schedule delay analysis and bottleneck identification."""
    return estimate_all_route_delays(db)


@app.get("/api/fleet/positions")
def get_fleet_positions(db: Session = Depends(get_db)):
    """
    Returns latest GPS and speed coordinates for all active buses and sensing nodes.
    """
    # Query latest timestamp per vehicle
    subq = db.query(
        FleetPosition.vehicle_id,
        func.max(FleetPosition.timestamp).label("max_ts")
    ).group_by(FleetPosition.vehicle_id).subquery()

    positions = db.query(FleetPosition).join(
        subq,
        (FleetPosition.vehicle_id == subq.c.vehicle_id) &
        (FleetPosition.timestamp == subq.c.max_ts)
    ).all()

    if not positions:
        # Fallback demonstration fleet when freshly started
        return [
            {"vehicle_id": "BUS-TN01-1042", "lat": 13.0067, "lon": 80.2030, "speed_kmh": 42.0, "road_name": "Guindy Kathipara", "status": "active", "timestamp": datetime.utcnow().isoformat()},
            {"vehicle_id": "BUS-TN02-3891", "lat": 13.0604, "lon": 80.2496, "speed_kmh": 38.0, "road_name": "Anna Salai (Mount Road)", "status": "active", "timestamp": datetime.utcnow().isoformat()},
            {"vehicle_id": "MUNICIPAL-TRUCK-07", "lat": 12.8231, "lon": 80.0442, "speed_kmh": 28.0, "road_name": "SRM Potheri Corridor", "status": "active", "timestamp": datetime.utcnow().isoformat()},
            {"vehicle_id": "PATROL-VAN-12", "lat": 12.9516, "lon": 80.1462, "speed_kmh": 46.0, "road_name": "GST Road (NH-32)", "status": "active", "timestamp": datetime.utcnow().isoformat()},
            {"vehicle_id": "BUS-TN22-5501", "lat": 12.9719, "lon": 80.2500, "speed_kmh": 34.0, "road_name": "Old Mahabalipuram Road", "status": "active", "timestamp": datetime.utcnow().isoformat()},
        ]

    return [
        {
            "vehicle_id": p.vehicle_id,
            "lat": p.lat,
            "lon": p.lon,
            "speed_kmh": p.speed_kmh,
            "road_name": p.road_name,
            "status": p.status,
            "last_detection_type": p.last_detection_type,
            "timestamp": p.timestamp.isoformat() if p.timestamp else datetime.utcnow().isoformat()
        }
        for p in positions
    ]


# Multi-City Deployment Scalability API (SIH Municipal Portability)
ACTIVE_CITY_KEY = "chennai"

SUPPORTED_CITIES = [
    {
        "key": "chennai",
        "display_name": "Chennai",
        "state": "Tamil Nadu",
        "center": {"lat": 13.0827, "lon": 80.2707},
        "zoom": 12,
        "municipal_body": "Greater Chennai Corporation (GCC)",
        "is_active": True,
    },
    {
        "key": "bangalore",
        "display_name": "Bengaluru",
        "state": "Karnataka",
        "center": {"lat": 12.9716, "lon": 77.5946},
        "zoom": 12,
        "municipal_body": "Bruhat Bengaluru Mahanagara Palike (BBMP)",
        "is_active": False,
    },
    {
        "key": "delhi",
        "display_name": "Delhi NCR",
        "state": "NCT Delhi",
        "center": {"lat": 28.6139, "lon": 77.2090},
        "zoom": 11,
        "municipal_body": "Municipal Corporation of Delhi (MCD)",
        "is_active": False,
    },
]

@app.get("/api/cities")
def get_deployment_cities():
    """Returns available municipal deployment configurations."""
    global ACTIVE_CITY_KEY
    for c in SUPPORTED_CITIES:
        c["is_active"] = (c["key"] == ACTIVE_CITY_KEY)
    return {"active": ACTIVE_CITY_KEY, "cities": SUPPORTED_CITIES}


@app.post("/api/cities/switch")
def switch_active_city(city_key: str = Query(...)):
    """Switches the active urban fleet spatial scope."""
    global ACTIVE_CITY_KEY
    matched = next((c for c in SUPPORTED_CITIES if c["key"] == city_key.lower()), None)
    if not matched:
        raise HTTPException(status_code=404, detail=f"City '{city_key}' not provisioned")
    ACTIVE_CITY_KEY = matched["key"]
    for c in SUPPORTED_CITIES:
        c["is_active"] = (c["key"] == ACTIVE_CITY_KEY)
    return {"status": "success", "switched_to": matched}

