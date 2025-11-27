import torch

class AnthropometricModule:
        def __init__(self, standard="ISO_8559"):
        if standard != "ISO_8559":
            raise ValueError("Supporte uniquement le standard ISO_8559")
        
        # Au lieu de listes de boucles fixes, on définit les LANDMARKS (points de repère)
        # qui définissent la HAUTEUR de la coupe ou les extrémités de la mesure.
        # Indices basés sur la topologie SMPL standard (6890 vertices).
        self.landmarks = {
            # Pour les circonférences (définit la hauteur de coupe)
            "chest_landmark": 3021,       # Mamelon gauche (approx) ou sternum
            "waist_landmark": 3500,       # Nombril (Belly button)
            "hip_landmark": 0,            # Bassin (Pelvis) - souvent ajusté un peu plus bas
            
            # Pour les largeurs (Point A à Point B)
            "left_shoulder": 412,         # Acromion Gauche
            "right_shoulder": 5419,       # Acromion Droit (symétrique approx)
        }

    def calculate_measurements(self, vertices, faces=None):
        """
        vertices: Tensor (6890, 3)
        faces: Tensor (F, 3) - Nécessaire pour la méthode de découpe précise (slicing)
        """
        measurements = {}
        
        # Conversion en numpy pour trimesh si nécessaire
        verts_np = vertices.detach().cpu().numpy()
        
        # --- MESURES DE LARGEUR (WIDTH) ---
        # Distance Euclidienne simple entre deux points
        p1 = vertices[self.landmarks["left_shoulder"]]
        p2 = vertices[self.landmarks["right_shoulder"]]
        width = torch.norm(p1 - p2)
        measurements["shoulder_width"] = width.item() * 100 # m -> cm

        # --- MESURES DE CIRCONFÉRENCE (SLICING) ---
        # Méthode : On coupe le mesh à la hauteur (Y) du landmark
        
        # Si vous n'avez pas les faces ou trimesh, voici une approximation pure torch
        # (Moins précis car cela suit les bords des triangles en zigzag)
        if faces is None:
            measurements.update(self._approximate_circumference(vertices))
        else:
            # Méthode précise avec Trimesh (Recommandée ISO 8559)
            faces_np = faces.detach().cpu().numpy()
            mesh = trimesh.Trimesh(vertices=verts_np, faces=faces_np, process=False)
            
            for name, landmark_idx in [("chest", self.landmarks["chest_landmark"]), 
                                       ("waist", self.landmarks["waist_landmark"]), 
                                       ("hip", self.landmarks["hip_landmark"])]:
                
                # 1. Obtenir la hauteur du point de repère
                height = verts_np[landmark_idx][1] # Axe Y est généralement la hauteur
                
                # 2. Couper le mesh par un plan horizontal à cette hauteur
                # section retourne un Path3D
                slice_section = mesh.section(plane_origin=[0, height, 0], 
                                             plane_normal=[0, 1, 0])
                
                if slice_section is None:
                    measurements[f"{name}_circumference"] = 0.0
                else:
                    # Calculer le périmètre (longueur totale de la coupe)
                    # slice_section peut contenir plusieurs boucles (bras + corps), 
                    # on prend généralement la plus grande (le corps)
                    try:
                        circumference = slice_section.length
                    except:
                        circumference = 0.0
                    
                    measurements[f"{name}_circumference"] = circumference * 100

        return measurements

    
