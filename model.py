import torch
import torch.nn as nn

from some_hmr_library import ViTBackbone, SMPLRegressor
from bypass_network import BypassNetwork

class FocusedHumanBodyModel(nn.Module):
    def __init__(self):
        super().__init__()
        
        self.backbone = ViTBackbone() 
        self.regressor = SMPLRegressor() 
        
        # Bypass Network (CNN + ResNet)
        self.bypass_net = BypassNetwork() 

    def forward(self, image):
        # forward propagation
        features = self.backbone(image)
        smpl_params = self.regressor(features) # output {'theta', 'beta', ...} 
        
        bypass_output = self.bypass_net(image)
        
        # Durant l'entrainement，'bypass_output' et 'smpl_params' seront tous entrés à 'DynamicLoss'
        # Quand on fait la prédiction, on s'intéresse que le 'smpl_params'
        if self.training:
            smpl_params['bypass_output'] = bypass_output
            
        return smpl_params
