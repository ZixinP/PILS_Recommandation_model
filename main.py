import torch
from PIL import Image
from torchvision import transforms

from model import FocusedHumanBodyModel
from smpl_wrapper import SMPLWrapper
from measurements import AnthropometricModule

# 
# "FocusedHumanBodyModel" est le modèle pré-entrainé
hmr_model = FocusedHumanBodyModel()
hmr_model.load_state_dict(torch.load("focused_model.pth"))
hmr_model.eval()

# Initialiser le modèle 
smplx_layer = SMPLWrapper(model_path="./smplx_models")
measurement_module = AnthropometricModule(standard="ISO_8559") 


input_image = Image.open("your_front_photo.jpg")

preprocess = transforms.Compose([
    transforms.Resize((512, 384)),
    transforms.ToTensor(),
])
input_tensor = preprocess(input_image).unsqueeze(0)

# HMR
with torch.no_grad():
    # model.forward() 
    pred_smpl_params = hmr_model(input_tensor)

    pred_beta = pred_smpl_params['beta'] 
    pred_theta = pred_smpl_params['theta']

# HBME : créer un 3D-grid et calculer
body_mesh_vertices = smplx_layer.get_mesh(pred_beta, pose_type='A-pose') 

# extraire les résultats de calcul
body_measurements = measurement_module.calculate_measurements(body_mesh_vertices)

print("SMPL (Beta):", pred_beta)
print("--- Measure du corps (cm) ---")
print(f":Tour de poitrine {body_measurements['chest_circumference']:.2f}")
print(f"Tour de taille: {body_measurements['waist_circumference']:.2f}") 
print(f"Tour de hanches: {body_measurements['hip_circumference']:.2f}")
print(f"Largeur d'épaules: {body_measurements['shoulder_width']:.2f}")
# Plus 
