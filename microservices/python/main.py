import os
import uuid
import numpy as np
import json
import cv2
import torch
import ultralytics.nn.tasks
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ultralytics import YOLO
from typing import Dict, Any, List, Optional

# Fix for PyTorch 2.6+ weights_only=True security change
# Monkey patch torch.load to default weights_only=False for this session
# We trust our local model files.
_original_load = torch.load
def safe_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_load(*args, **kwargs)
torch.load = safe_load

# Import SMPL Fitter
# Ensure smpl_fitter.py is in the same directory
try:
    from smpl_fitter import SMPLFitter
except ImportError:
    print("smpl_fitter module not found. SMPL features disabled.")
    SMPLFitter = None

# --- Configuration ---
app = FastAPI(title="FashionistAI Python Microservice")
UPLOAD_DIR = "uploads"
SIZE_CHARTS_DIR = "size_charts"
MODELS_DIR = "models"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# Charger les modèles YOLOv8
try:
    model_pose = YOLO('yolov8n-pose.pt')
    model_seg = YOLO('yolov8n-seg.pt')
except Exception as e:
    raise RuntimeError(f"Erreur lors du chargement des modèles YOLO : {e}")

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

# --- Fonctions de calcul (Geometric / Hybrid) ---
def get_distance(p1, p2):
    return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def calculate_measurements_geometric(k_front, k_side, user_height_cm, mask_front=None, mask_side=None):
    """
    Advanced Geometric Calculation using Dual-View Keypoints and Segmentation Masks.
    Approximates body cross-sections as ellipses using Width (Front) and Depth (Side).
    """
    if k_front is None or len(k_front) < 17:
        raise ValueError("Keypoints invalid.")

    # 1. Establish Scale (cm per pixel)
    # Use vertical distance between Eyes (1,2) and Ankles (15,16) for robust height
    # Front view
    eye_y = (k_front[1][1] + k_front[2][1]) / 2
    ankle_y = (k_front[15][1] + k_front[16][1]) / 2
    pixel_height = abs(ankle_y - eye_y)
    
    # Anthropometric ratio: Eye-to-Floor is approx 93.6% of total height
    # So scale = (Height * 0.936) / pixel_height
    if pixel_height == 0: return None
    scale = (user_height_cm * 0.936) / pixel_height

    # 2. Limb Lengths (Multi-segment polyline)
    # Arm: Shoulder(5/6) -> Elbow(7/8) -> Wrist(9/10)
    left_arm = get_distance(k_front[5], k_front[7]) + get_distance(k_front[7], k_front[9])
    right_arm = get_distance(k_front[6], k_front[8]) + get_distance(k_front[8], k_front[10])
    arm_length = ((left_arm + right_arm) / 2) * scale

    # Leg: Hip(11/12) -> Knee(13/14) -> Ankle(15/16)
    left_leg = get_distance(k_front[11], k_front[13]) + get_distance(k_front[13], k_front[15])
    right_leg = get_distance(k_front[12], k_front[14]) + get_distance(k_front[14], k_front[16])
    leg_length = ((left_leg + right_leg) / 2) * scale

    # 3. Widths & Depths (from Masks if available, else Keypoints)
    
    # Define Y-levels for measurements based on skeleton
    shoulder_y = (k_front[5][1] + k_front[6][1]) / 2
    hip_y = (k_front[11][1] + k_front[12][1]) / 2
    torso_len = abs(hip_y - shoulder_y)
    
    chest_y = int(shoulder_y + torso_len * 0.3) # Chest approx 30% down torso
    waist_y = int(shoulder_y + torso_len * 0.75) # Waist approx 75% down torso (narrowest point)
    
    def get_mask_width(mask, y):
        if mask is None: return None
        y = int(y)
        if y < 0 or y >= mask.shape[0]: return None
        row = mask[y, :]
        if not np.any(row): return None
        indices = np.where(row)[0]
        return (indices[-1] - indices[0]) * scale

    # --- Shoulder Width ---
    # Keypoint width
    shoulder_width_kp = get_distance(k_front[5], k_front[6]) * scale
    # Mask width (usually wider than bone)
    shoulder_width_mask = get_mask_width(mask_front, shoulder_y)
    # Use mask if available, else KP * 1.2 (bone to skin)
    shoulder_width = shoulder_width_mask if shoulder_width_mask else (shoulder_width_kp * 1.2)

    # --- Chest ---
    chest_width_kp = (get_distance(k_front[5], k_front[6]) + get_distance(k_front[11], k_front[12])) / 2 * scale # Avg shoulder/hip
    chest_width = get_mask_width(mask_front, chest_y) or chest_width_kp
    
    # Chest Depth (Side)
    # If mask_side available, measure at same relative height
    # Need to map Front Y to Side Y. Assuming cropped similarly or full body.
    # Simple mapping: normalized height %
    chest_depth = 0
    if mask_side is not None:
        # Re-calculate scale/y for side
        s_eye_y = (k_side[1][1] + k_side[2][1]) / 2
        s_ankle_y = (k_side[15][1] + k_side[16][1]) / 2
        s_height = abs(s_ankle_y - s_eye_y)
        s_scale = (user_height_cm * 0.936) / s_height if s_height > 0 else scale
        
        s_shoulder_y = (k_side[5][1] + k_side[6][1]) / 2
        s_hip_y = (k_side[11][1] + k_side[12][1]) / 2
        s_torso_len = abs(s_hip_y - s_shoulder_y)
        s_chest_y = int(s_shoulder_y + s_torso_len * 0.3)
        
        # Get width in side view = Depth
        row = mask_side[s_chest_y, :] if (0 <= s_chest_y < mask_side.shape[0]) else None
        if row is not None and np.any(row):
             indices = np.where(row)[0]
             chest_depth = (indices[-1] - indices[0]) * s_scale
    
    if chest_depth == 0:
        chest_depth = chest_width * 0.75 # Default ratio if side view fails

    # --- Waist ---
    waist_width_kp = get_distance(k_front[11], k_front[12]) * scale
    waist_width = get_mask_width(mask_front, waist_y) or (waist_width_kp * 1) # Hips are wider than waist usually, this is approx
    
    waist_depth = 0
    if mask_side is not None:
        s_waist_y = int(s_shoulder_y + s_torso_len * 0.7)
        row = mask_side[s_waist_y, :] if (0 <= s_waist_y < mask_side.shape[0]) else None
        if row is not None and np.any(row):
             indices = np.where(row)[0]
             waist_depth = (indices[-1] - indices[0]) * s_scale
             
    if waist_depth == 0:
        waist_depth = waist_width * 0.7 # Default ratio

    # 4. Calculate Circumferences (Ramanujan Ellipse Approximation)
    # C ≈ π * [3(a+b) - sqrt((3a+b)(a+3b))] where a, b are semi-axes
    def calc_ellipse_circ(width, depth):
        a = width / 2
        b = depth / 2
        return np.pi * (3*(a+b) - np.sqrt((3*a+b)*(a+3*b)))

    chest_circ = calc_ellipse_circ(chest_width, chest_depth)
    waist_circ = calc_ellipse_circ(waist_width, waist_depth)

    # 5. Apply User Adjustments (Multipliers)
    return {
        "shoulder_width": round(shoulder_width * 0.9, 1),
        "waist_width": round(waist_width, 1), # Internal debug
        "arm_length": round(arm_length * 1.05, 1),
        "leg_length": round(leg_length * 1.15, 1),
        "estimated_chest_circumference": round(chest_circ * 0.60, 1),
        "estimated_waist_circumference": round(waist_circ * 0.55, 1),
        "method": "geometric_hybrid_2d"
    }

# --- Point d'API ---
@app.post("/analyze-pose")
async def analyze_pose(image_front: UploadFile = File(...), image_side: UploadFile = File(...), height: str = Form(...)):
    try:
        user_height = float(height)
    except ValueError:
        raise HTTPException(status_code=400, detail="La taille doit être un nombre.")

    # Save images
    def save_upload_file(upload_file):
        file_extension = upload_file.filename.split('.')[-1]
        filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as buffer:
            return file_path, buffer
            
    # Process Front Image
    file_path_front = ""
    file_path_side = ""
    
    try:
        # Save Front
        file_extension_front = image_front.filename.split('.')[-1]
        file_path_front = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_front.{file_extension_front}")
        with open(file_path_front, "wb") as buffer:
            buffer.write(await image_front.read())

        # Save Side
        file_extension_side = image_side.filename.split('.')[-1]
        file_path_side = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_side.{file_extension_side}")
        with open(file_path_side, "wb") as buffer:
            buffer.write(await image_side.read())

        # 1. YOLO Detection (Front) - Pose
        results_front_pose = model_pose(file_path_front, verbose=False)
        if not results_front_pose or not results_front_pose[0].keypoints:
             raise HTTPException(status_code=404, detail="Aucune personne détectée sur la photo de face (Pose).")
        
        keypoints_front = results_front_pose[0].keypoints.xy[0].cpu().numpy()
        orig_shape = results_front_pose[0].orig_shape 
        image_size = (orig_shape[1], orig_shape[0])

        if len(keypoints_front) < 17:
             raise HTTPException(status_code=400, detail="Détection de pose incomplète (Face).")

        # 1b. YOLO Segmentation (Front) - Mask
        results_front_seg = model_seg(file_path_front, verbose=False)
        mask_front = None
        if results_front_seg and results_front_seg[0].masks:
             # Get the mask of the first detected person
             # masks.data is (N, H, W) tensor
             mask_front = results_front_seg[0].masks.data[0].cpu().numpy()
             # Resize mask to original image size if needed (YOLO might output smaller masks)
             if mask_front.shape != orig_shape:
                 mask_front = cv2.resize(mask_front, (orig_shape[1], orig_shape[0]))

        # 2. YOLO Detection (Side) - Pose
        results_side_pose = model_pose(file_path_side, verbose=False)
        if not results_side_pose or not results_side_pose[0].keypoints:
             raise HTTPException(status_code=404, detail="Aucune personne détectée sur la photo de profil (Pose).")
        
        keypoints_side = results_side_pose[0].keypoints.xy[0].cpu().numpy()
        
        if len(keypoints_side) < 17:
             raise HTTPException(status_code=400, detail="Détection de pose incomplète (Profil).")

        # 2b. YOLO Segmentation (Side) - Mask
        results_side_seg = model_seg(file_path_side, verbose=False)
        mask_side = None
        if results_side_seg and results_side_seg[0].masks:
             mask_side = results_side_seg[0].masks.data[0].cpu().numpy()
             if mask_side.shape != results_side_seg[0].orig_shape:
                 orig_shape_side = results_side_seg[0].orig_shape
                 mask_side = cv2.resize(mask_side, (orig_shape_side[1], orig_shape_side[0]))

        # 3. SMPL Fitting (Hybrid)
        smpl_data = None
        measurements = None
        
        if smpl_fitter and smpl_fitter.model_available:
            try:
                print("Running Hybrid SMPL + Segmentation optimization...")
                # Pass both front and side keypoints AND masks
                fit_result = smpl_fitter.fit(
                    keypoints_front, keypoints_side, 
                    image_size, user_height,
                    mask_front=mask_front, mask_side=mask_side
                )
                if fit_result:
                    measurements = fit_result['measurements']
                    measurements['method'] = "hybrid_seg_3d"
                    
                    measurements['estimated_chest_circumference'] = measurements['chest_circumference_cm']
                    measurements['estimated_waist_circumference'] = measurements['waist_circumference_cm']
                    
                    smpl_data = {
                        "vertices": fit_result['vertices'].tolist(),
                        "faces": fit_result['faces'].tolist()
                    }
            except Exception as e:
                print(f"SMPL fitting failed: {e}. Falling back to heuristic.")
                import traceback
                traceback.print_exc()
        
        # 4. Fallback to Geometric Hybrid (Using Masks + Keypoints)
        if measurements is None:
            print("Using Geometric Hybrid fallback.")
            measurements = calculate_measurements_geometric(
                keypoints_front, keypoints_side, user_height,
                mask_front=mask_front, mask_side=mask_side
            )
            smpl_data = None

    except (ValueError, IndexError) as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors du calcul : {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne du serveur : {e}")
    finally:
        if os.path.exists(file_path_front):
             os.remove(file_path_front)
        if os.path.exists(file_path_side):
             os.remove(file_path_side)

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
    best_size = None
    min_total_diff = float('inf')
    
    for size_info in size_chart:
        total_diff = 0.0
        valid_criteria_count = 0
        
        for criteria, range_values in size_info.items():
            if criteria in ["label", "unit"]: continue
            
            measurement_key = None
            if criteria == "chest": measurement_key = "estimated_chest_circumference"
            elif criteria == "waist": measurement_key = "estimated_waist_circumference"
            elif criteria == "hips": measurement_key = "hip_circumference_cm" # basic support
            
            if measurement_key and measurement_key in measurements:
                val = measurements[measurement_key]
                valid_criteria_count += 1
                
                # Check fit
                min_val, max_val = range_values[0], range_values[1]
                if val < min_val:
                    total_diff += (min_val - val)
                elif val > max_val:
                    total_diff += (val - max_val)
                # else: diff is 0 (perfect fit for this criteria)
        
        # If no criteria matched (e.g. searching for inseam but we don't have it), skip
        if valid_criteria_count == 0:
            continue
            
        if total_diff < min_total_diff:
            min_total_diff = total_diff
            best_size = size_info["label"]
            
    return best_size

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)