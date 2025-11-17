import torch
import torch.nn as nn

class DynamicLoss(nn.Module):
    def __init__(self, measurement_vertices_indices, non_measurement_vertices_indices):
        super().__init__()
        self.l2_loss = nn.MSELoss()

        # On définit les 2 parties : un sera mesuré et l'autre pas
        self.meas_indices = measurement_vertices_indices
        self.non_meas_indices = non_measurement_vertices_indices

    def forward(self, pred_params, gt_params, pred_vertices, gt_vertices, epoch):
        loss_theta = self.l2_loss(pred_params['theta'], gt_params['theta'])
        loss_beta = self.l2_loss(pred_params['beta'], gt_params['beta'])
        loss_para = loss_theta + loss_beta 
        
        # 
        v_meas_pred = pred_vertices[:, self.meas_indices]
        v_meas_gt = gt_vertices[:, self.meas_indices]
        
        v_non_meas_pred = pred_vertices[:, self.non_meas_indices]
        v_non_meas_gt = gt_vertices[:, self.non_meas_indices]

        # Loss des 2 parties
        loss_meas_part = self.l2_loss(v_meas_pred, v_meas_gt)
        loss_non_meas_part = self.l2_loss(v_non_meas_pred, v_non_meas_gt)
        
        # alpha est un poid qui sera ajusté au cours d'entrâinement
        alpha = min(0.5, epoch / 100.0) 
        
        # L_coord est combiné des loss de 2 parties, alpha est initialement définie à 0 : le modèle ne se concentre qu'à le loss de la partie mesuré
        loss_coord = (1.0 - alpha) * loss_meas_part + alpha * loss_non_meas_part 

    
        lambda_coord = 0.2
        lambda_para = 0.1
        total_loss = lambda_coord * loss_coord + lambda_para * loss_para
        
        return total_loss
