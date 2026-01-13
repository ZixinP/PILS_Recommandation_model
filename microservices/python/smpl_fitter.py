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
        
        # Check for SMPL or SMPLX model files
        smpl_path = os.path.join(model_path, f'SMPL_{gender.upper()}.pkl')
        smplx_path = os.path.join(model_path, 'smplx', f'SMPLX_{gender.upper()}.pkl')
        
        if os.path.exists(smpl_path):
            self.model_type = 'smpl'
            self.model_available = True
            print(f"[INFO] Found SMPL model: {smpl_path}")
        elif os.path.exists(smplx_path):
            self.model_type = 'smplx'
            self.model_available = True
            print(f"[INFO] Found SMPLX model: {smplx_path}")
        else:
            self.model_type = None
            self.model_available = False
            print(f"Warning: Neither SMPL nor SMPLX model found in {model_path}.")
        
        if self.model_available:
            # Load the detected model
            self.smpl = smplx.create(model_path, model_type=self.model_type, gender=gender, ext='pkl').to(self.device)
            self.faces = self.smpl.faces
        else:
            self.smpl = None

    def fit(self, keypoints_front, keypoints_side, image_size, height_cm=170.0, mask_front=None, mask_side=None):
        """
        Fit SMPL model to 2D keypoints using optimization from two views (Front + Side).
        
        Args:
            keypoints_front: (17, 2) numpy array of YOLO keypoints (Front view)
            keypoints_side: (17, 2) numpy array of YOLO keypoints (Side view)
            image_size: (width, height) tuple
            height_cm: User height in cm
            mask_front: (H, W) numpy array binary mask (Front)
            mask_side: (H, W) numpy array binary mask (Side)
        
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
        kp_front_target = torch.tensor(keypoints_front, dtype=torch.float32).to(self.device)
        kp_side_target = torch.tensor(keypoints_side, dtype=torch.float32).to(self.device)
        
        # --- Optimization Parameters ---
        global_orient = torch.zeros(1, 3, requires_grad=True, device=self.device)
        body_pose = torch.zeros(1, 69, requires_grad=True, device=self.device)
        betas = torch.zeros(1, 10, requires_grad=True, device=self.device)
        translation = torch.tensor([[0.0, 0.0, 50.0]], dtype=torch.float32, requires_grad=True, device=self.device)
        
        # Optimizer
        optimizer = optim.Adam([global_orient, body_pose, betas, translation], lr=0.02)
        
        # Mapping YOLO (17) to SMPL (24)
        yolo_indices = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        smpl_indices = [16, 17, 18, 19, 20, 21, 1, 2, 4, 5, 7, 8]
        
        # Rotation Matrix for 90 degrees (Side View)
        theta = np.pi / 2 # 90 degrees
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        rotation_matrix = torch.tensor([
            [cos_t, 0, sin_t],
            [0, 1, 0],
            [-sin_t, 0, cos_t]
        ], dtype=torch.float32).to(self.device)

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
            
            joints_3d = output.joints[0] # (24, 3) or (45, 3)
            
            # --- FRONT VIEW PROJECTION ---
            relevant_joints_3d = joints_3d[smpl_indices]
            relevant_targets_front = kp_front_target[yolo_indices]
            
            focal_length = 5000.0
            cx, cy = image_size[0] / 2, image_size[1] / 2
            
            pred_front_x = focal_length * (relevant_joints_3d[:, 0] + translation[:, 0]) / (relevant_joints_3d[:, 2] + translation[:, 2]) + cx
            pred_front_y = focal_length * (relevant_joints_3d[:, 1] + translation[:, 1]) / (relevant_joints_3d[:, 2] + translation[:, 2]) + cy
            pred_front = torch.stack([pred_front_x, pred_front_y], dim=1)
            
            # --- SIDE VIEW PROJECTION ---
            joints_3d_side = torch.matmul(relevant_joints_3d, rotation_matrix)
            relevant_targets_side = kp_side_target[yolo_indices]
            
            pred_side_x = focal_length * (joints_3d_side[:, 0] + translation[:, 0]) / (joints_3d_side[:, 2] + translation[:, 2]) + cx
            pred_side_y = focal_length * (joints_3d_side[:, 1] + translation[:, 1]) / (joints_3d_side[:, 2] + translation[:, 2]) + cy
            pred_side = torch.stack([pred_side_x, pred_side_y], dim=1)

            # Loss
            loss_front = nn.MSELoss()(pred_front, relevant_targets_front)
            loss_side = nn.MSELoss()(pred_side, relevant_targets_side)
            
            loss_shape = torch.mean(betas ** 2) * 0.01 
            loss_pose = torch.mean(body_pose ** 2) * 0.01 
            
            total_loss = loss_front + loss_side + loss_shape + loss_pose
            
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
            min_y = np.min(vertices[:, 1])
            max_y = np.max(vertices[:, 1])
            mesh_height = max_y - min_y
            
            target_height_m = height_cm / 100.0
            scale_factor = target_height_m / mesh_height
            
            vertices = vertices * scale_factor
            
            # Use Segmentation Masks for measurements if available, else fallback to SMPL mesh
            if mask_front is not None and mask_side is not None:
                print("[INFO] Using Segmentation Masks for precise measurements.")
                measurements = self.extract_measurements_from_masks(mask_front, mask_side, height_cm)
            else:
                print("[INFO] Using SMPL Mesh for measurements (Segmentation masks missing).")
                measurements = self.extract_measurements(vertices)
            
            return {
                'vertices': vertices,
                'faces': self.faces,
                'measurements': measurements,
                'betas': betas.cpu().numpy().tolist(),
                'pose': body_pose.cpu().numpy().tolist()
            }

    def extract_measurements_from_masks(self, mask_front, mask_side, height_cm):
        """
        Calculate measurements using pixel widths from Front and Side masks.
        """
        # 1. Determine Pixel-to-CM scale from Front Mask
        # Find top and bottom pixels of the person
        rows_front = np.any(mask_front, axis=1)
        if not np.any(rows_front): return self.extract_measurements(np.zeros((1,3))) # Fallback
        
        y_min_front, y_max_front = np.where(rows_front)[0][[0, -1]]
        pixel_height_front = y_max_front - y_min_front
        
        scale = height_cm / pixel_height_front # cm per pixel
        
        # 2. Define Anatomical Heights (Relative to bounding box top)
        # Head is at 0, Feet at pixel_height
        # Neck/Shoulders: ~18% from top
        # Chest: ~28% from top (or 72% from bottom)
        # Waist: ~42% from top (or 58% from bottom)
        # Hips: ~50% from top
        
        def get_width_at_y(mask, y_pct):
            y_idx = int(y_min_front + pixel_height_front * y_pct)
            y_idx = np.clip(y_idx, 0, mask.shape[0]-1)
            row = mask[y_idx, :]
            if not np.any(row): return 0
            x_min, x_max = np.where(row)[0][[0, -1]]
            return (x_max - x_min) * scale
        
        # For Side mask, we need its own height analysis to align Y-axis
        rows_side = np.any(mask_side, axis=1)
        if not np.any(rows_side): return self.extract_measurements(np.zeros((1,3))) # Fallback
        y_min_side, y_max_side = np.where(rows_side)[0][[0, -1]]
        pixel_height_side = y_max_side - y_min_side
        scale_side = height_cm / pixel_height_side # Should be similar
        
        def get_depth_at_y(mask, y_pct):
            y_idx = int(y_min_side + pixel_height_side * y_pct)
            y_idx = np.clip(y_idx, 0, mask.shape[0]-1)
            row = mask[y_idx, :]
            if not np.any(row): return 0
            x_min, x_max = np.where(row)[0][[0, -1]]
            return (x_max - x_min) * scale_side

        # Shoulder Width (Front Width only) at ~18% from top
        shoulder_width = get_width_at_y(mask_front, 0.18)
        
        # Chest (Front Width + Side Depth) at ~28% from top
        chest_width = get_width_at_y(mask_front, 0.28)
        chest_depth = get_depth_at_y(mask_side, 0.28)
        
        # Waist (Front Width + Side Depth) at ~42% from top
        waist_width = get_width_at_y(mask_front, 0.42)
        waist_depth = get_depth_at_y(mask_side, 0.42)
        
        # Circumference Formula: Ellipse perimeter approx = PI * sqrt(2 * (a^2 + b^2)) is WRONG.
        # Correct approx: PI * sqrt((w^2 + d^2)/2) where w, d are diameters (axes lengths)?
        # Standard: L = pi * (3(a+b) - sqrt((3a+b)(a+3b))) is Ramanujan.
        # Simple: PI * sqrt((w*w + d*d)/2) is fine for clothes.
        # w and d are diameters. a=w/2, b=d/2.
        
        chest_circ = np.pi * np.sqrt((chest_width**2 + chest_depth**2) / 2)
        waist_circ = np.pi * np.sqrt((waist_width**2 + waist_depth**2) / 2)
        
        # Limbs (Heuristic based on height)
        arm_length = height_cm * 0.35 * 1.05
        leg_length = height_cm * 0.48 * 1.05
        
        # Apply Adjustments
        shoulder_width_adj = shoulder_width * 0.9
        chest_circ_adj = chest_circ * 0.60
        waist_circ_adj = waist_circ * 0.55
        arm_length_adj = arm_length * 1.05
        leg_length_adj = leg_length * 1.15
        
        # Return
        return {
            "height_cm": round(height_cm, 1),
            "chest_circumference_cm": round(chest_circ_adj, 1),
            "waist_circumference_cm": round(waist_circ_adj, 1),
            "hip_circumference_cm": round(0, 1),
            
            "shoulder_width": round(shoulder_width_adj, 1),
            "estimated_chest_circumference": round(chest_circ_adj, 1),
            "estimated_waist_circumference": round(waist_circ_adj, 1),
            "arm_length": round(arm_length_adj, 1),
            "leg_length": round(leg_length_adj, 1)
        }

    def extract_measurements(self, vertices):
        """
        Extract measurements from the mesh and apply user-requested adjustments.
        """
        # Create trimesh object
        mesh = trimesh.Trimesh(vertices=vertices, faces=self.faces, process=False)
        
        # 1. Height
        min_y, max_y = mesh.bounds[:, 1]
        total_height = max_y - min_y
        
        # 2. Chest (approximate height: 72% of total height from bottom)
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
            
        # 4. Shoulder Width (approximate height: 82% of total height)
        # We take the width (x-extent) of the slice
        shoulder_height = min_y + total_height * 0.82
        shoulder_slice = mesh.section(plane_origin=[0, shoulder_height, 0], plane_normal=[0, 1, 0])
        shoulder_width = 0
        if shoulder_slice:
            shoulder_width = shoulder_slice.bounds[1][0] - shoulder_slice.bounds[0][0]

        # 5. Limb Lengths (Heuristic based on height if joints aren't available easily here)
        # Standard anthropometric ratios: Arm ~ 0.35 * H, Leg ~ 0.48 * H
        arm_length = total_height * 0.35
        leg_length = total_height * 0.48
        
        # --- Apply User Requested Adjustments ---
        shoulder_width_adj = shoulder_width * 0.9
        chest_circ_adj = chest_circ * 0.60
        waist_circ_adj = waist_circ * 0.55
        arm_length_adj = arm_length * 1.05
        leg_length_adj = leg_length * 1.15

        return {
            "height_cm": round(total_height * 100, 1),
            "chest_circumference_cm": round(chest_circ_adj * 100, 1),
            "waist_circumference_cm": round(waist_circ_adj * 100, 1),
            "hip_circumference_cm": round(0, 1), # Not requested to adjust, placeholer
            
            # Frontend expects these keys:
            "shoulder_width": round(shoulder_width_adj * 100, 1),
            "estimated_chest_circumference": round(chest_circ_adj * 100, 1),
            "estimated_waist_circumference": round(waist_circ_adj * 100, 1),
            "arm_length": round(arm_length_adj * 100, 1),
            "leg_length": round(leg_length_adj * 100, 1)
        }
