// Types pour les mesures corporelles
export interface Measurements {
  hauteur_estimee: number;  // en cm
  largeur_epaules: number;  // en cm
  tour_poitrine: number;    // en cm
  tour_taille: number;      // en cm
  longueur_bras: number;    // en cm
  confiance: number;        // 0.0 à 1.0
}

// Types pour les vêtements détectés
export interface DetectedClothes {
  type: string;
  confiance: number;        // 0.0 à 1.0
  couleur_dominante: string;
  bbox: [number, number, number, number]; // [x, y, width, height]
}

// Réponse de l'API d'analyse
export interface AnalysisResponse {
  success: boolean;
  measurements: Measurements;
  detected_clothes: DetectedClothes[];
  message: string;
}

// Props pour le composant PhotoCapture
export interface PhotoCaptureProps {
  onAnalysisStart: () => void;
  onAnalysisComplete: (data: AnalysisResponse) => void;
  onAnalysisEnd: () => void;
  isLoading: boolean;
}

// Props pour le composant MeasurementsDisplay
export interface MeasurementsDisplayProps {
  measurements: Measurements | null;
  detectedClothes: DetectedClothes[];
  isLoading: boolean;
}
