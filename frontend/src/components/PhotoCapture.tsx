import React, { useState, useRef } from 'react';
import Webcam from 'react-webcam';
import './PhotoCapture.css';
import { API_CONFIG } from '../config';

interface SilhouetteSVGProps {
  isFilter?: boolean;
}

const SilhouetteSVG: React.FC<SilhouetteSVGProps> = ({ isFilter = false }) => (
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
            
            {/* Torse - côté gauche */}
            <path d="M 70 75 Q 68 95, 70 120 Q 72 145, 75 170" />
            
            {/* Torse - côté droit */}
            <path d="M 130 75 Q 132 95, 130 120 Q 128 145, 125 170" />
            
            {/* Taille */}
            <path d="M 75 170 Q 82 172, 100 172 Q 118 172, 125 170" />
            
            {/* Hanches - côté gauche */}
            <path d="M 75 170 Q 72 185, 75 205" />
            
            {/* Hanches - côté droit */}
            <path d="M 125 170 Q 128 185, 125 205" />
            
            {/* Entrejambe */}
            <path d="M 75 205 Q 85 210, 100 212" />
            <path d="M 125 205 Q 115 210, 100 212" />
            
            {/* Jambe gauche - cuisse */}
            <path d="M 75 205 Q 72 240, 70 280" />
            {/* Jambe gauche - mollet */}
            <path d="M 70 280 Q 68 320, 66 360 Q 65 390, 64 420" />
            
            {/* Jambe droite - cuisse */}
            <path d="M 125 205 Q 128 240, 130 280" />
            {/* Jambe droite - mollet */}
            <path d="M 130 280 Q 132 320, 134 360 Q 135 390, 136 420" />
            
            {/* Jambe gauche - intérieur cuisse */}
            <path d="M 100 212 Q 88 240, 82 280" />
            {/* Jambe gauche - intérieur mollet */}
            <path d="M 82 280 Q 78 320, 76 360 Q 74 390, 72 420" />
            
            {/* Jambe droite - intérieur cuisse */}
            <path d="M 100 212 Q 112 240, 118 280" />
            {/* Jambe droite - intérieur mollet */}
            <path d="M 118 280 Q 122 320, 124 360 Q 126 390, 128 420" />
            
            {/* Pieds */}
            <path d="M 64 420 Q 60 428, 58 432 L 72 432 L 72 425" />
            <path d="M 136 420 Q 140 428, 142 432 L 128 432 L 128 425" />
        </g>
        
        {!isFilter && (
            <g stroke="rgba(255,255,255,0.7)" strokeWidth="1" strokeDasharray="4,4" fill="white">
                {/* Lignes de mesure - Épaules */}
                <line x1="60" y1="75" x2="140" y2="75" />
                <circle cx="60" cy="75" r="2.5" />
                <circle cx="140" cy="75" r="2.5" />
                
                {/* Lignes de mesure - Poitrine */}
                <line x1="68" y1="105" x2="132" y2="105" />
                <circle cx="68" cy="105" r="2.5" />
                <circle cx="132" cy="105" r="2.5" />
                
                {/* Lignes de mesure - Taille */}
                <line x1="75" y1="170" x2="125" y2="170" />
                <circle cx="75" cy="170" r="2.5" />
                <circle cx="125" cy="170" r="2.5" />
                
                {/* Ligne de mesure - Bras gauche */}
                <line x1="40" y1="75" x2="40" y2="180" />
                <circle cx="40" cy="75" r="2.5" />
                <circle cx="40" cy="180" r="2.5" />
                
                {/* Ligne de mesure - Jambe */}
                <line x1="50" y1="205" x2="50" y2="420" />
                <circle cx="50" cy="205" r="2.5" />
                <circle cx="50" cy="420" r="2.5" />
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

type Step = 'capture' | 'preview' | 'results';

interface BodyMeasurementAppProps {
    initialImage?: string;
    triggerCapture?: number;
}

const BodyMeasurementApp: React.FC<BodyMeasurementAppProps> = ({ initialImage, triggerCapture }) => {
    const webcamRef = useRef<Webcam>(null);
    const [height, setHeight] = useState<string>('');
    const [measurements, setMeasurements] = useState<MeasurementsData | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string>('');
    const [imgSrc, setImgSrc] = useState<string | null>(null);
    const [step, setStep] = useState<Step>('capture');
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

    // Mettre à jour l'image si elle est fournie depuis le mobile
    React.useEffect(() => {
        if (initialImage) {
            setImgSrc(initialImage);
            setStep('preview');
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
                setImgSrc(imageSrc);
                setStep('preview');
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

        if (!imgSrc) {
            setError('Aucune image à analyser.');
            setIsLoading(false);
            return;
        }

        const response = await fetch(imgSrc);
        const blob = await response.blob();
        const file = new File([blob], "capture.jpeg", { type: "image/jpeg" });
        const formData = new FormData();
        formData.append('image', file);
        formData.append('height', height);

        try {
            const apiResponse = await fetch(`${API_CONFIG.BACKEND_URL}/api/analyze-pose`, { method: 'POST', body: formData });
            if (!apiResponse.ok) {
                const errData = await apiResponse.json();
                throw new Error(errData.detail || 'Erreur du serveur');
            }
            const result = await apiResponse.json();
            setMeasurements(result.measurements as MeasurementsData);
            setStep('results');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Une erreur est survenue');
        } finally {
            setIsLoading(false);
        }
    };

    const reset = (): void => {
        setMeasurements(null);
        setError('');
        setImgSrc(null);
        setHeight('');
        setStep('capture');
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
                {step === 'capture' && (
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
                    </>
                )}
                {step === 'preview' && imgSrc && <img src={imgSrc} alt="Aperçu de la capture" className="preview-image" />}
            </div>

            {step === 'capture' && !isCameraLoading && <SilhouetteSVG isFilter={true} />}

            {step === 'results' && measurements && (
                <div className="results-overlay">
                    <SilhouetteSVG />
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
                 {step === 'capture' && !isCameraLoading && (
                     <button onClick={handleCapture} className="submit-btn">Capturer</button>
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
                                        // Déclencher automatiquement la recommandation lors du changement
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