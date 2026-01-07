import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import smplx
import trimesh
import os
import json

class SMPLFitter:
    def __init__(self, model_path='models', gender='neutral', device='cpu'):
        self.device = torch.device(device)
        self.model_path = model_path
        self.gender = gender
        
        # Check if model file exists
        model_file = os.path.join(model_path, f'SMPL_{gender.upper()}.pkl')
        self.model_available = os.path.exists(model_file)
        
        if self.model_available:
            # Load SMPL model
            # We use 'smplx.create' but specifically asking for 'smpl' model_type
            self.smpl = smplx.create(model_path, model_type='smpl', gender=gender).to(self.device)
            self.faces = self.smpl.faces
        else:
            print(f"⚠️ Warning: SMPL model not found at {model_file}. 3D features will be disabled.")
            self.smpl = None

    def fit(self, keypoints_2d, image_size, height_cm=170.0):
        """
        Fit SMPL model to 2D keypoints using optimization.
        
        Args:
            keypoints_2d: (17, 2) numpy array of YOLO keypoints
            image_size: (width, height) tuple
            height_cm: User height in cm
        
        Returns:
            dict: {
                'vertices': numpy array (6890, 3),
                'faces': numpy array,
                'measurements': dict
            }
        """
        if not self.model_available:
            return None

        # Convert to torch tensors
        kp_2d_target = torch.tensor(keypoints_2d, dtype=torch.float32).to(self.device)
        
        # --- Optimization Parameters ---
        # We optimize:
        # 1. global_orient (3) - Rotation of the body
        # 2. body_pose (23*3 = 69) - Joint rotations
        # 3. betas (10) - Body shape
        # 4. translation (3) - Camera translation / global position
        # 5. scale (1) - Global scale
        
        global_orient = torch.zeros(1, 3, requires_grad=True, device=self.device)
        body_pose = torch.zeros(1, 69, requires_grad=True, device=self.device)
        betas = torch.zeros(1, 10, requires_grad=True, device=self.device)
        translation = torch.tensor([[0.0, 0.0, 50.0]], dtype=torch.float32, requires_grad=True, device=self.device)
        
        # Optimizer
        optimizer = optim.Adam([global_orient, body_pose, betas, translation], lr=0.02)
        
        # Mapping YOLO (17) to SMPL (24)
        # This is an approximation. 
        # YOLO: 0:Nose, 5:LSh, 6:RSh, 7:LElb, 8:RElb, 9:LWri, 10:RWri, 11:LHip, 12:RHip, 13:LKnee, 14:RKnee, 15:LAnk, 16:RAnk
        # SMPL (Basic): 0:Pelvis, 1:LHip, 2:RHip, 4:LKnee, 5:RKnee, 7:LAnk, 8:RAnk, ... 12:Neck, 16:LSh, 17:RSh, 18:LElb, 19:RElb, 20:LWri, 21:RWri
        
        # Indices in SMPL joints output that correspond to YOLO keypoints
        # Note: SMPL joints regressor output usually includes 24 joints.
        # We need to map them carefully.
        
        # Valid pairs (YOLO_idx, SMPL_idx)
        # 5 (LSh) <-> 16
        # 6 (RSh) <-> 17
        # 7 (LElb) <-> 18
        # 8 (RElb) <-> 19
        # 9 (LWri) <-> 20
        # 10 (RWri) <-> 21
        # 11 (LHip) <-> 1
        # 12 (RHip) <-> 2
        # 13 (LKnee) <-> 4
        # 14 (RKnee) <-> 5
        # 15 (LAnk) <-> 7
        # 16 (RAnk) <-> 8
        
        yolo_indices = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        smpl_indices = [16, 17, 18, 19, 20, 21, 1, 2, 4, 5, 7, 8]
        
        # Optimization Loop
        iterations = 100
        for i in range(iterations):
            optimizer.zero_grad()
            
            # Forward pass
            output = self.smpl(
                betas=betas,
                global_orient=global_orient,
                body_pose=body_pose,
                transl=translation,
                return_verts=True
            )
            
            # Project 3D joints to 2D
            # Simple weak perspective projection: (x,y) = (X/Z + cx, Y/Z + cy)
            # Or simplified: scale * (X, Y) + translation_2d
            
            joints_3d = output.joints[0] # (24, 3) or (45, 3)
            
            # Extract relevant joints
            relevant_joints_3d = joints_3d[smpl_indices]
            relevant_targets_2d = kp_2d_target[yolo_indices]
            
            # Project
            # Note: We are simulating a camera.
            # Assume orthographic for simplicity in this "poor man's" fitter, 
            # or perspective if we had intrinsics.
            # Here we let the 'translation' variable handle the Z depth (perspective division).
            
            # Perspective projection
            # x_screen = f * (x / z) + cx
            focal_length = 5000.0 # Approximate
            cx, cy = image_size[0] / 2, image_size[1] / 2
            
            pred_2d_x = focal_length * (relevant_joints_3d[:, 0] + translation[:, 0]) / (relevant_joints_3d[:, 2] + translation[:, 2]) + cx
            pred_2d_y = focal_length * (relevant_joints_3d[:, 1] + translation[:, 1]) / (relevant_joints_3d[:, 2] + translation[:, 2]) + cy
            
            pred_2d = torch.stack([pred_2d_x, pred_2d_y], dim=1)
            
            # Loss
            loss_reproj = nn.MSELoss()(pred_2d, relevant_targets_2d)
            loss_shape = torch.mean(betas ** 2) * 0.01 # Regularize shape
            loss_pose = torch.mean(body_pose ** 2) * 0.01 # Regularize pose
            
            total_loss = loss_reproj + loss_shape + loss_pose
            
            total_loss.backward()
            optimizer.step()
            
        # --- Final Mesh Generation ---
        with torch.no_grad():
            output = self.smpl(
                betas=betas,
                global_orient=global_orient,
                body_pose=body_pose,
                transl=translation,
                return_verts=True
            )
            vertices = output.vertices[0].cpu().numpy()
            
            # Scale mesh to match real world height
            # Current mesh is in meters (roughly).
            # We enforce the user's height.
            
            # Calculate mesh height
            min_y = np.min(vertices[:, 1])
            max_y = np.max(vertices[:, 1])
            mesh_height = max_y - min_y
            
            # Scaling factor
            target_height_m = height_cm / 100.0
            scale_factor = target_height_m / mesh_height
            
            # Apply scale
            vertices = vertices * scale_factor
            
            # Recalculate measurements on the scaled mesh
            measurements = self.extract_measurements(vertices)
            
            return {
                'vertices': vertices,
                'faces': self.faces,
                'measurements': measurements,
                'betas': betas.cpu().numpy().tolist(),
                'pose': body_pose.cpu().numpy().tolist()
            }

    def extract_measurements(self, vertices):
        """
        Extract girths using slicing.
        Vertices indices for SMPL are standard.
        """
        # We can use specific vertices landmarks or slicing.
        # Slicing is more robust.
        
        # Create trimesh object
        mesh = trimesh.Trimesh(vertices=vertices, faces=self.faces, process=False)
        
        # 1. Height (already known, but good to check)
        min_y, max_y = mesh.bounds[:, 1]
        total_height = max_y - min_y
        
        # 2. Chest (approximate height: 75% of total height from bottom)
        chest_height = min_y + total_height * 0.72
        chest_slice = mesh.section(plane_origin=[0, chest_height, 0], plane_normal=[0, 1, 0])
        chest_circ = 0
        if chest_slice:
            chest_circ = chest_slice.length
            
        # 3. Waist (approximate height: 58% of total height)
        waist_height = min_y + total_height * 0.58
        waist_slice = mesh.section(plane_origin=[0, waist_height, 0], plane_normal=[0, 1, 0])
        waist_circ = 0
        if waist_slice:
            waist_circ = waist_slice.length
            
        # 4. Hips (approximate height: 50% of total height)
        hip_height = min_y + total_height * 0.48
        hip_slice = mesh.section(plane_origin=[0, hip_height, 0], plane_normal=[0, 1, 0])
        hip_circ = 0
        if hip_slice:
            hip_circ = hip_slice.length
            
        return {
            "height_cm": round(total_height * 100, 1),
            "chest_circumference_cm": round(chest_circ * 100, 1),
            "waist_circumference_cm": round(waist_circ * 100, 1),
            "hip_circumference_cm": round(hip_circ * 100, 1)
        }
