import os
import uuid
import numpy as np
import json
import cv2
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ultralytics import YOLO
from typing import Dict, Any, List, Optional

# Import SMPL Fitter
# Ensure smpl_fitter.py is in the same directory
try:
    from smpl_fitter import SMPLFitter
except ImportError:
    print("⚠️ smpl_fitter module not found. SMPL features disabled.")
    SMPLFitter = None

# --- Configuration ---
app = FastAPI(title="FashionistAI Python Microservice")
UPLOAD_DIR = "uploads"
SIZE_CHARTS_DIR = "size_charts"
MODELS_DIR = "models"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# Charger le modèle YOLOv8-Pose pré-entraîné
try:
    model = YOLO('yolov8n-pose.pt')
except Exception as e:
    raise RuntimeError(f"Erreur lors du chargement du modèle YOLO : {e}")

# Initialize SMPL Fitter
smpl_fitter = None
if SMPLFitter:
    smpl_fitter = SMPLFitter(model_path=MODELS_DIR, gender='neutral')

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Fonctions de calcul (Fallback / Legacy) ---
def get_pixel_distance(p1, p2):
    return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def calculate_measurements_heuristic(keypoints_data, user_height_cm):
    """
    Heuristic calculation (Fallback if SMPL is not available).
    """
    if keypoints_data is None or len(keypoints_data) < 17:
        raise ValueError("Données de points clés invalides ou incomplètes.")

    k = keypoints_data

    shoulder_mid_y = (k[5][1] + k[6][1]) / 2
    ankle_mid_y = (k[15][1] + k[16][1]) / 2
    pixel_height = abs(ankle_mid_y - shoulder_mid_y)
    body_height_cm = user_height_cm * 0.80

    if pixel_height == 0:
        raise ValueError("Hauteur en pixels nulle.")
    
    pixel_to_cm_ratio = body_height_cm / pixel_height

    shoulder_width_px = get_pixel_distance(k[5], k[6])
    shoulder_width_cm = shoulder_width_px * pixel_to_cm_ratio

    waist_width_px = get_pixel_distance(k[11], k[12])
    waist_width_cm = waist_width_px * pixel_to_cm_ratio

    left_arm_px = get_pixel_distance(k[5], k[7]) + get_pixel_distance(k[7], k[9])
    right_arm_px = get_pixel_distance(k[6], k[8]) + get_pixel_distance(k[8], k[10])
    arm_length_cm = ((left_arm_px + right_arm_px) / 2) * pixel_to_cm_ratio

    left_leg_px = get_pixel_distance(k[11], k[13]) + get_pixel_distance(k[13], k[15])
    right_leg_px = get_pixel_distance(k[12], k[14]) + get_pixel_distance(k[14], k[16])
    leg_length_cm = ((left_leg_px + right_leg_px) / 2) * pixel_to_cm_ratio

    chest_circumference_cm = shoulder_width_cm * np.pi * 0.9
    waist_circumference_cm = waist_width_cm * np.pi

    return {
        "shoulder_width": round(shoulder_width_cm, 1),
        "waist_width": round(waist_width_cm, 1),
        "arm_length": round(arm_length_cm, 1),
        "leg_length": round(leg_length_cm, 1),
        "estimated_chest_circumference": round(chest_circumference_cm, 1),
        "estimated_waist_circumference": round(waist_circumference_cm, 1),
        "method": "heuristic_2d"
    }

# --- Point d'API ---
@app.post("/analyze-pose")
async def analyze_pose(image: UploadFile = File(...), height: str = Form(...)):
    try:
        user_height = float(height)
    except ValueError:
        raise HTTPException(status_code=400, detail="La taille doit être un nombre.")

    # Save image
    file_extension = image.filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await image.read())

    try:
        # 1. YOLO Detection
        results = model(file_path, verbose=False)
        if not results or not results[0].keypoints:
             raise HTTPException(status_code=404, detail="Aucune personne détectée sur l'image.")
        
        # Get Keypoints
        keypoints = results[0].keypoints.xy[0].cpu().numpy()
        orig_shape = results[0].orig_shape # (height, width)
        image_size = (orig_shape[1], orig_shape[0]) # (width, height)

        if len(keypoints) < 17:
             raise HTTPException(status_code=400, detail="Détection de pose incomplète.")

        # 2. SMPL Fitting (if available)
        smpl_data = None
        measurements = None
        
        if smpl_fitter and smpl_fitter.model_available:
            try:
                print("Running SMPL optimization...")
                fit_result = smpl_fitter.fit(keypoints, image_size, user_height)
                if fit_result:
                    measurements = fit_result['measurements']
                    measurements['method'] = "smpl_3d"
                    
                    # Add compatibility keys for existing frontend/recommender
                    measurements['estimated_chest_circumference'] = measurements['chest_circumference_cm']
                    measurements['estimated_waist_circumference'] = measurements['waist_circumference_cm']
                    
                    # Prepare mesh data for frontend (subsampled to reduce size if needed)
                    # For now send full vertices
                    smpl_data = {
                        "vertices": fit_result['vertices'].tolist(),
                        "faces": fit_result['faces'].tolist()
                    }
            except Exception as e:
                print(f"SMPL fitting failed: {e}. Falling back to heuristic.")
        
        # 3. Fallback to Heuristic
        if measurements is None:
            measurements = calculate_measurements_heuristic(keypoints, user_height)
            smpl_data = None

    except (ValueError, IndexError) as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors du calcul : {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne du serveur : {e}")
    finally:
        if os.path.exists(file_path):
             os.remove(file_path)

    response = {
        "message": "Analyse réussie", 
        "measurements": measurements
    }
    
    if smpl_data:
        response["mesh_data"] = smpl_data
        
    return response

@app.get("/health")
async def health_check():
    smpl_status = "active" if (smpl_fitter and smpl_fitter.model_available) else "inactive (model missing)"
    return {
        "status": "ok", 
        "service": "FashionistAI Python Microservice",
        "smpl_status": smpl_status
    }

@app.get("/brands")
async def get_brands():
    try:
        if not os.path.exists(SIZE_CHARTS_DIR):
            raise HTTPException(status_code=404, detail="Répertoire size_charts introuvable")
        brands = [f[:-5] for f in os.listdir(SIZE_CHARTS_DIR) if f.endswith('.json')]
        return {"brands": sorted(brands)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SizeRecommendationRequest(BaseModel):
    measurements: Dict[str, float]
    brand_name: str
    category: str

@app.post("/recommend-size")
async def recommend_size(request: SizeRecommendationRequest):
    try:
        json_file_path = os.path.join(SIZE_CHARTS_DIR, f"{request.brand_name}.json")
        if not os.path.exists(json_file_path):
            raise HTTPException(status_code=404, detail=f"Marque '{request.brand_name}' non trouvée.")
        
        with open(json_file_path, 'r', encoding='utf-8') as f:
            size_data = json.load(f)
        
        categories_data = size_data.get("categories", {})
        results = {}
        
        # Helper logic for matching sizes
        def find_size(category_key, result_key):
            cat_data = categories_data.get(category_key, {})
            if request.category in cat_data:
                results[result_key] = get_best_fit_size(request.measurements, cat_data[request.category])
            else:
                results[result_key] = None
                
        find_size("male", "male_size")
        find_size("female", "female_size")
        
        return {
            "brand": request.brand_name,
            "category": request.category,
            "recommendations": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_best_fit_size(measurements: Dict[str, float], size_chart: List[Dict[str, Any]]) -> Optional[str]:
    for size_info in size_chart:
        is_fit = True
        for criteria, range_values in size_info.items():
            if criteria in ["label", "unit"]: continue
            
            measurement_key = None
            if criteria == "chest": measurement_key = "estimated_chest_circumference"
            elif criteria == "waist": measurement_key = "estimated_waist_circumference"
            
            if measurement_key and measurement_key in measurements:
                val = measurements[measurement_key]
                if not (range_values[0] <= val <= range_values[1]):
                    is_fit = False
                    break
        if is_fit: return size_info["label"]
    return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)