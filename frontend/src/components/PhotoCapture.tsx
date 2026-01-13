import React, { useState, useRef } from 'react';
import Webcam from 'react-webcam';
import SMPLViewer from './SMPLViewer';
import './PhotoCapture.css';
import { API_CONFIG } from '../config';

interface SilhouetteSVGProps {
  isFilter?: boolean;
  view?: 'front' | 'side';
}

const SilhouetteSVG: React.FC<SilhouetteSVGProps> = ({ isFilter = false, view = 'front' }) => (
    <svg viewBox="0 0 200 500" className="silhouette-svg" style={{ zIndex: isFilter ? 5 : 11 }}>
        <defs>
            <linearGradient id="silhouetteGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style={{ stopColor: isFilter ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.5)', stopOpacity: 1 }} />
                <stop offset="100%" style={{ stopColor: isFilter ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.3)', stopOpacity: 1 }} />
            </linearGradient>
        </defs>
        <g 
            stroke={isFilter ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.6)"} 
            strokeWidth={isFilter ? "3" : "2.5"} 
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            {view === 'front' ? (
                <>
                    {/* Tête ovale */}
                    <ellipse cx="100" cy="35" rx="18" ry="22" />
                    {/* Cou */}
                    <path d="M 88 52 Q 90 58, 92 62" />
                    <path d="M 112 52 Q 110 58, 108 62" />
                    {/* Épaules et début du torse */}
                    <path d="M 92 62 Q 85 68, 70 75" />
                    <path d="M 108 62 Q 115 68, 130 75" />
                    {/* Bras gauche */}
                    <path d="M 70 75 Q 60 85, 55 100 Q 52 115, 50 135 Q 49 155, 52 175" />
                    {/* Main gauche */}
                    <ellipse cx="52" cy="180" rx="6" ry="8" />
                    {/* Bras droit */}
                    <path d="M 130 75 Q 140 85, 145 100 Q 148 115, 150 135 Q 151 155, 148 175" />
                    {/* Main droite */}
                    <ellipse cx="148" cy="180" rx="6" ry="8" />
                    {/* Torse */}
                    <path d="M 70 75 Q 68 95, 70 120 Q 72 145, 75 170" />
                    <path d="M 130 75 Q 132 95, 130 120 Q 128 145, 125 170" />
                    {/* Taille */}
                    <path d="M 75 170 Q 82 172, 100 172 Q 118 172, 125 170" />
                    {/* Hanches */}
                    <path d="M 75 170 Q 72 185, 75 205" />
                    <path d="M 125 170 Q 128 185, 125 205" />
                    {/* Entrejambe */}
                    <path d="M 75 205 Q 85 210, 100 212" />
                    <path d="M 125 205 Q 115 210, 100 212" />
                    {/* Jambes */}
                    <path d="M 75 205 Q 72 240, 70 280" />
                    <path d="M 70 280 Q 68 320, 66 360 Q 65 390, 64 420" />
                    <path d="M 125 205 Q 128 240, 130 280" />
                    <path d="M 130 280 Q 132 320, 134 360 Q 135 390, 136 420" />
                    <path d="M 100 212 Q 88 240, 82 280" />
                    <path d="M 82 280 Q 78 320, 76 360 Q 74 390, 72 420" />
                    <path d="M 100 212 Q 112 240, 118 280" />
                    <path d="M 118 280 Q 122 320, 124 360 Q 126 390, 128 420" />
                    {/* Pieds */}
                    <path d="M 64 420 Q 60 428, 58 432 L 72 432 L 72 425" />
                    <path d="M 136 420 Q 140 428, 142 432 L 128 432 L 128 425" />
                </>
            ) : (
                <>
                     {/* SIDE VIEW SILHOUETTE (Simplified) */}
                    {/* Tête */}
                    <ellipse cx="100" cy="35" rx="16" ry="22" />
                    {/* Cou */}
                    <path d="M 95 56 L 95 62" />
                    <path d="M 105 56 L 105 62" />
                    {/* Dos */}
                    <path d="M 90 62 Q 80 100, 85 170" />
                    {/* Ventre */}
                    <path d="M 110 62 Q 125 100, 115 170" />
                    {/* Jambe (une seule visible/profil) */}
                    <path d="M 85 170 L 85 420" />
                    <path d="M 115 170 L 115 420" />
                    {/* Bras */}
                    <path d="M 100 65 L 100 180" />
                </>
            )}
        </g>
        
        {!isFilter && view === 'front' && (
            <g stroke="rgba(255,255,255,0.7)" strokeWidth="1" strokeDasharray="4,4" fill="white">
                {/* Lignes de mesure - Épaules */}
                <line x1="60" y1="75" x2="140" y2="75" />
                <circle cx="60" cy="75" r="2.5" />
                <circle cx="140" cy="75" r="2.5" />
            </g>
        )}
    </svg>
);

interface MeasurementsData {
    shoulder_width: string;
    estimated_chest_circumference: string;
    estimated_waist_circumference: string;
    arm_length: string;
    leg_length: string;
}

type Step = 'capture-front' | 'capture-side' | 'preview' | 'results';

interface BodyMeasurementAppProps {
    initialImage?: string;
    triggerCapture?: number;
}

const BodyMeasurementApp: React.FC<BodyMeasurementAppProps> = ({ initialImage, triggerCapture }) => {
    const webcamRef = useRef<Webcam>(null);
    const [height, setHeight] = useState<string>('');
    const [measurements, setMeasurements] = useState<MeasurementsData | null>(null);
    const [meshData, setMeshData] = useState<any>(null);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string>('');
    const [imgFront, setImgFront] = useState<string | null>(null);
    const [imgSide, setImgSide] = useState<string | null>(null);
    const [step, setStep] = useState<Step>('capture-front');
    const [isCameraLoading, setCameraLoading] = useState<boolean>(true);
    const [showBrandSelection, setShowBrandSelection] = useState<boolean>(false);
    const [brands, setBrands] = useState<string[]>([]);
    const [selectedBrand, setSelectedBrand] = useState<string>('');
    const [sizeRecommendation, setSizeRecommendation] = useState<any>(null);

    // Charger la liste des marques au montage
    React.useEffect(() => {
        const fetchBrands = async () => {
            try {
                const response = await fetch(`${API_CONFIG.BACKEND_URL}/brands`);
                const data = await response.json();
                setBrands(data.brands || []);
            } catch (error) {
                console.error('Erreur lors du chargement des marques:', error);
            }
        };
        fetchBrands();
    }, []);

    // Mettre à jour l'image si elle est fournie depuis le mobile (Assume it's Front for now)
    React.useEffect(() => {
        if (initialImage) {
            setImgFront(initialImage);
            setStep('capture-side');
        }
    }, [initialImage]);

    // Déclencher la capture quand triggerCapture change (signal du mobile)
    React.useEffect(() => {
        if (triggerCapture && triggerCapture > 0) {
            console.log('🎯 Capture déclenchée par le mobile!');
            handleCapture();
        }
    }, [triggerCapture]);

    const handleCapture = (): void => {
        if (webcamRef.current) {
            const imageSrc = webcamRef.current.getScreenshot();
            if (imageSrc) {
                if (step === 'capture-front') {
                    setImgFront(imageSrc);
                    setStep('capture-side');
                } else if (step === 'capture-side') {
                    setImgSide(imageSrc);
                    setStep('preview');
                }
            } else {
                setError("Impossible de capturer l'image. Assurez-vous d'avoir autorisé l'accès à la caméra.");
            }
        }
    };

    const analyzeImage = async (): Promise<void> => {
        if (!height) {
            setError('Veuillez entrer votre taille.');
            return;
        }
        setIsLoading(true);
        setError('');

        if (!imgFront || !imgSide) {
            setError('Images manquantes.');
            setIsLoading(false);
            return;
        }

        const blobFront = await (await fetch(imgFront)).blob();
        const blobSide = await (await fetch(imgSide)).blob();
        
        const fileFront = new File([blobFront], "front.jpeg", { type: "image/jpeg" });
        const fileSide = new File([blobSide], "side.jpeg", { type: "image/jpeg" });
        
        const formData = new FormData();
        formData.append('image_front', fileFront);
        formData.append('image_side', fileSide);
        formData.append('height', height);

        try {
            const apiResponse = await fetch(`${API_CONFIG.BACKEND_URL}/api/analyze-pose`, { method: 'POST', body: formData });
            if (!apiResponse.ok) {
                const errData = await apiResponse.json();
                throw new Error(errData.detail || 'Erreur du serveur');
            }
            const result = await apiResponse.json();
            setMeasurements(result.measurements as MeasurementsData);
            if (result.mesh_data) {
                setMeshData(result.mesh_data);
            }
            setStep('results');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Une erreur est survenue');
        } finally {
            setIsLoading(false);
        }
    };

    const reset = (): void => {
        setMeasurements(null);
        setMeshData(null);
        setError('');
        setImgFront(null);
        setImgSide(null);
        setHeight('');
        setStep('capture-front');
        setShowBrandSelection(false);
        setSelectedBrand('');
        setSizeRecommendation(null);
    };

    const handleNextClick = (): void => {
        setShowBrandSelection(true);
    };

    const handleGetSizeRecommendation = async (brandName?: string): Promise<void> => {
        const brand = brandName || selectedBrand;
        
        if (!brand || !measurements) {
            console.log('❌ Pas de marque ou de mesures');
            return;
        }

        setIsLoading(true);
        setError('');
        
        try {
            const requestBody = {
                measurements: {
                    estimated_chest_circumference: parseFloat(measurements.estimated_chest_circumference),
                    estimated_waist_circumference: parseFloat(measurements.estimated_waist_circumference),
                },
                brand_name: brand,
                category: 'tops',
            };

            console.log('📤 Envoi de la requête:', requestBody);

            const response = await fetch(`${API_CONFIG.BACKEND_URL}/recommend-size`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody),
            });

            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }

            const data = await response.json();
            console.log('📥 Réponse reçue:', data);
            setSizeRecommendation(data);
        } catch (error) {
            console.error('❌ Erreur lors de la recommandation de taille:', error);
            setError('Erreur lors de la recommandation de taille');
        } finally {
            setIsLoading(false);
        }
    };

    const handleUserMediaError = (err: string | DOMException): void => {
        if (typeof err === 'string') {
            setError(`Erreur caméra: ${err}`);
        } else if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
            setError("Accès caméra bloqué. Vérifiez les réglages de l'app Chrome dans les Réglages de votre iPhone.");
        } else {
            setError(`Erreur caméra: ${err.name}. Veuillez autoriser l'accès.`);
        }
        setCameraLoading(false);
    };

    return (
        <div className={`capture-container step-${step}`}>
            <div className="webcam-wrapper">
                {(step === 'capture-front' || step === 'capture-side') && (
                    <>
                        {isCameraLoading && <div className="camera-loader">Chargement de la caméra...</div>}
                        <Webcam 
                            audio={false} 
                            ref={webcamRef} 
                            screenshotFormat="image/jpeg" 
                            videoConstraints={{ width: 720, height: 1280, facingMode: "user" }} 
                            mirrored={true} 
                            className="webcam-video"
                            onUserMedia={() => setCameraLoading(false)}
                            onUserMediaError={handleUserMediaError}
                        />
                        <div className="instruction-overlay">
                            {step === 'capture-front' ? '1. PHOTO DE FACE' : '2. PHOTO DE PROFIL (Tournez de 90°)'}
                        </div>
                    </>
                )}
                {step === 'preview' && (
                    <div className="preview-container" style={{ display: 'flex', gap: '10px', overflowX: 'auto' }}>
                        {imgFront && <img src={imgFront} alt="Aperçu Face" className="preview-image" style={{ width: '48%', objectFit: 'cover' }} />}
                        {imgSide && <img src={imgSide} alt="Aperçu Profil" className="preview-image" style={{ width: '48%', objectFit: 'cover' }} />}
                    </div>
                )}
            </div>

            {(step === 'capture-front' || step === 'capture-side') && !isCameraLoading && (
                <SilhouetteSVG isFilter={true} view={step === 'capture-front' ? 'front' : 'side'} />
            )}

            {step === 'results' && measurements && (
                <div className="results-overlay">
                    {meshData ? (
                        <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 5 }}>
                            <SMPLViewer meshData={meshData} />
                        </div>
                    ) : (
                        <SilhouetteSVG view='front' />
                    )}
                    <div className="measurement-item center" style={{ top: '13%' }}>
                        <label>Épaules</label>
                        <input 
                            name="shoulder_width" 
                            value={`${measurements.shoulder_width} cm`}
                            readOnly
                        />
                    </div>
                    <div className="measurement-item center" style={{ top: '22%' }}>
                        <label>Poitrine</label>
                        <input 
                            name="estimated_chest_circumference" 
                            value={`${measurements.estimated_chest_circumference} cm`}
                            readOnly
                        />
                    </div>
                    <div className="measurement-item center" style={{ top: '35%' }}>
                        <label>Taille</label>
                        <input 
                            name="estimated_waist_circumference" 
                            value={`${measurements.estimated_waist_circumference} cm`}
                            readOnly
                        />
                    </div>
                    <div className="measurement-item" style={{ top: '20%', left: '8%' }}>
                        <label>Bras</label>
                        <input 
                            name="arm_length" 
                            value={`${measurements.arm_length} cm`}
                            readOnly
                        />
                    </div>
                    <div className="measurement-item" style={{ top: '64%', left: '8%' }}>
                        <label>Jambe</label>
                        <input 
                            name="leg_length" 
                            value={`${measurements.leg_length} cm`}
                            readOnly
                        />
                    </div>
                </div>
            )}
            
            <div className="controls-overlay">
                 {(step === 'capture-front' || step === 'capture-side') && !isCameraLoading && (
                     <button onClick={handleCapture} className="submit-btn">
                         {step === 'capture-front' ? 'Capturer Face' : 'Capturer Profil'}
                     </button>
                 )}
                {step === 'preview' && (
                    <>
                        <input 
                            type="number" 
                            value={height} 
                            onChange={(e) => setHeight(e.target.value)} 
                            placeholder="Entrez votre taille en cm" 
                            className="height-input" 
                        />
                        <div className="button-group">
                             <button onClick={reset} className="retake-btn">Reprendre</button>
                             <button onClick={analyzeImage} disabled={isLoading} className="submit-btn">
                                 {isLoading ? 'Analyse...' : 'Analyser'}
                             </button>
                        </div>
                    </>
                )}
                {step === 'results' && (
                    <>
                        {showBrandSelection ? (
                            <div className="brand-selection-overlay">
                                <h3>Choisir une Marque</h3>
                                <select 
                                    value={selectedBrand} 
                                    onChange={(e) => {
                                        const brand = e.target.value;
                                        setSelectedBrand(brand);
                                        if (brand) {
                                            handleGetSizeRecommendation(brand);
                                        } else {
                                            setSizeRecommendation(null);
                                        }
                                    }}
                                    className="brand-dropdown"
                                >
                                    <option value="">-- Sélectionner --</option>
                                    {brands.map((brand) => (
                                        <option key={brand} value={brand}>{brand}</option>
                                    ))}
                                </select>

                                {isLoading && (
                                    <div style={{ textAlign: 'center', padding: '15px', color: '#007bff' }}>
                                        <strong>Chargement de la recommandation...</strong>
                                    </div>
                                )}

                                {sizeRecommendation && !isLoading && (
                                    <div className="size-recommendation-section">
                                        <h3 style={{ marginTop: '20px', fontSize: '16px' }}>Recommandation</h3>
                                        <div className="size-results">
                                            {sizeRecommendation.recommendations.male_size && (
                                                <div className="size-card">
                                                    <span>Homme:</span>
                                                    <strong>{sizeRecommendation.recommendations.male_size}</strong>
                                                </div>
                                            )}
                                            {sizeRecommendation.recommendations.female_size && (
                                                <div className="size-card">
                                                    <span>Femme:</span>
                                                    <strong>{sizeRecommendation.recommendations.female_size}</strong>
                                                </div>
                                            )}
                                            {!sizeRecommendation.recommendations.male_size && !sizeRecommendation.recommendations.female_size && (
                                                <p style={{ textAlign: 'center', color: '#666', margin: '10px 0' }}>
                                                    Aucune taille disponible pour ces mesures
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                )}

                                <div className="button-group" style={{ marginTop: '15px' }}>
                                    <button onClick={() => { setShowBrandSelection(false); setSizeRecommendation(null); setSelectedBrand(''); }} className="retake-btn">Retour</button>
                                    <button onClick={reset} className="submit-btn">Recommencer</button>
                                </div>
                            </div>
                        ) : (
                            <div className="button-group">
                                <button onClick={reset} className="submit-btn">Recommencer</button>
                                <button onClick={handleNextClick} className="next-btn">Suivant</button>
                            </div>
                        )}
                    </>
                )}
                {error && <p className="error-message">{error}</p>}
            </div>
        </div>
    );
};

export type { BodyMeasurementAppProps };
export default BodyMeasurementApp;