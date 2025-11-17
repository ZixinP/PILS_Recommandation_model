import torch

class AnthropometricModule:
    def __init__(self, standard="ISO_8559"):
        if standard != "ISO_8559":
            raise ValueError("Support que le standard ISO_8559") 
        
        # Definition des points sur le corps à mesurer
        # self.chest_loop_indices = [100, 101, 105, 120, ...] 
        # self.waist_loop_indices = [500, 501, 503, 510, ...]
        self.measurement_definitions = self.load_measurement_indices()

    # entrer un json file contenant les indices comme au-dessous
    def load_measurement_indices(self):
        return {
            "chest_circumference": [/*...points_list...*/],
            "waist_circumference": [/*...points_list...*/],
            "hip_circumference": [/*...points_list...*/],
            "shoulder_width": [/*...two-points_list...*/],
        }

    # mesurer à partir d'un 3D-grid
    def calculate_measurements(self, vertices):
        measurements = {}
        
        for name, indices in self.measurement_definitions.items():
            if "circumference" in name:
                loop_vertices = vertices[indices]
                
                distances = torch.sum(
                    torch.abs(loop_vertices - torch.roll(loop_vertices, shifts=1, dims=0)),
                    dim=1
                )
                circumference = torch.sum(distances)
                measurements[name] = circumference.item() * 100 # (m -> cm)
                
            elif "width" in name:
                p1 = vertices[indices[0]]
                p2 = vertices[indices[1]]
                width = torch.norm(p1 - p2)
                measurements[name] = width.item() * 100 # (m -> cm)
        
        return measurements
