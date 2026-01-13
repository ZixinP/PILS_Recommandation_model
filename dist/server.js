import express from 'express';
import { createServer } from 'http';
import { Server as SocketIOServer } from 'socket.io';
import cors from 'cors';
import QRCode from 'qrcode';
import multer from 'multer';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';
import config from './config.js';
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
// Initialize Express App
const app = express();
const httpServer = createServer(app);
// Initialize Socket.IO
const io = new SocketIOServer(httpServer, config.socketIO);
// Middleware
app.use(cors(config.cors));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
// Configure Multer for file upload
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        const uploadDir = join(__dirname, '..', config.upload.dest);
        if (!fs.existsSync(uploadDir)) {
            fs.mkdirSync(uploadDir, { recursive: true });
        }
        cb(null, uploadDir);
    },
    filename: (req, file, cb) => {
        const uniqueName = `${uuidv4()}-${file.originalname}`;
        cb(null, uniqueName);
    }
});
const upload = multer({
    storage,
    limits: { fileSize: config.upload.maxSize }
});
const sessions = new Map();
const socketToSession = new Map();
// ====================
// API ROUTES
// ====================
// Health check
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        service: 'FashionistAI TypeScript Backend',
        pythonService: config.pythonService.url,
        version: '2.0.0'
    });
});
// Generate QR Code
app.get('/api/generate-qr', async (req, res) => {
    try {
        const sessionId = req.query.sessionId || uuidv4();
        console.log(`📱 Generating QR code for session: ${sessionId}`);
        if (!sessions.has(sessionId)) {
            sessions.set(sessionId, {
                pcSocketId: sessionId,
                mobileSocketId: null,
                status: 'waiting',
                createdAt: Date.now()
            });
        }
        const mobileUrl = `http://${config.networkIP}:${config.port}/mobile-capture?session=${sessionId}`;
        console.log(`✅ Generated QR code with URL: ${mobileUrl}`);
        const qrCodeDataURL = await QRCode.toDataURL(mobileUrl, {
            width: 300,
            margin: 2,
            color: {
                dark: '#667eea',
                light: '#ffffff'
            }
        });
        res.json({
            success: true,
            sessionId,
            qrCode: qrCodeDataURL,
            mobileUrl
        });
    }
    catch (error) {
        console.error('❌ Error generating QR code:', error);
        res.status(500).json({
            success: false,
            error: 'Failed to generate QR code'
        });
    }
});
// Analyze pose via Python microservice
app.post('/api/analyze-pose', upload.fields([{ name: 'image_front', maxCount: 1 }, { name: 'image_side', maxCount: 1 }]), async (req, res) => {
    const filesCleanup = [];
    try {
        const files = req.files;
        if (!files || !files['image_front'] || !files['image_side']) {
            return res.status(400).json({
                success: false,
                detail: 'Both image_front and image_side are required'
            });
        }
        const fileFront = files['image_front'][0];
        const fileSide = files['image_side'][0];
        // Add to cleanup list
        filesCleanup.push(fileFront.path);
        filesCleanup.push(fileSide.path);
        const { height } = req.body;
        if (!height) {
            return res.status(400).json({
                success: false,
                detail: 'Height parameter is required'
            });
        }
        console.log(`🔍 Analyzing pose for height: ${height}cm`);
        // Send to Python microservice avec axios (meilleur support pour FormData avec fichiers)
        const FormData = (await import('form-data')).default;
        const formData = new FormData();
        formData.append('image_front', fs.createReadStream(fileFront.path), fileFront.filename);
        formData.append('image_side', fs.createReadStream(fileSide.path), fileSide.filename);
        formData.append('height', height);
        const response = await axios.post(`${config.pythonService.url}/analyze-pose`, formData, {
            headers: formData.getHeaders(),
            timeout: 20000 // Increased timeout for dual image processing
        });
        // Delete temporary files
        filesCleanup.forEach(path => {
            if (fs.existsSync(path))
                fs.unlinkSync(path);
        });
        console.log(`✅ Pose analyzed successfully`);
        res.json(response.data);
    }
    catch (error) {
        const errMsg = error.message || 'Error analyzing image';
        console.error('❌ Error analyzing pose:', errMsg);
        // Cleanup files on error
        filesCleanup.forEach(path => {
            if (fs.existsSync(path))
                fs.unlinkSync(path);
        });
        // Handle axios errors
        if (error.code === 'ECONNABORTED' || errMsg.includes('timeout')) {
            return res.status(504).json({
                success: false,
                detail: 'Le microservice Python ne répond pas (timeout).'
            });
        }
        if (error.code === 'ECONNREFUSED') {
            return res.status(502).json({
                success: false,
                detail: 'Connexion refusée vers le microservice Python.'
            });
        }
        res.status(500).json({
            success: false,
            detail: error.response?.data?.detail || errMsg
        });
    }
});
// Mobile capture page - redirection vers le frontend React
app.get('/mobile-capture', (req, res) => {
    const { session } = req.query;
    if (!session || !sessions.has(session)) {
        return res.status(404).send('<h1>Session invalide ou expirée</h1>');
    }
    // Rediriger vers le frontend React
    const frontendUrl = `http://${config.networkIP}:3000/mobile-capture?session=${session}`;
    res.redirect(frontendUrl);
});
// Route pour obtenir la liste des marques depuis le microservice Python
app.get('/brands', async (req, res) => {
    try {
        const response = await axios.get(`${config.pythonService.url}/brands`, {
            timeout: 5000
        });
        res.json(response.data);
    }
    catch (error) {
        console.error('❌ Erreur lors de la récupération des marques:', error.message);
        res.status(500).json({ error: 'Erreur lors de la récupération des marques' });
    }
});
// Route pour obtenir une recommandation de taille depuis le microservice Python
app.post('/recommend-size', async (req, res) => {
    try {
        const response = await axios.post(`${config.pythonService.url}/recommend-size`, req.body, {
            timeout: 5000,
            headers: {
                'Content-Type': 'application/json'
            }
        });
        res.json(response.data);
    }
    catch (error) {
        console.error('❌ Erreur lors de la recommandation de taille:', error.message);
        res.status(500).json({ error: 'Erreur lors de la recommandation de taille' });
    }
});
// ====================
// WEBSOCKET
// ====================
io.on('connection', (socket) => {
    console.log(`🔌 Client connected: ${socket.id}`);
    // PC joins with session ID
    socket.on('pc-join', ({ sessionId }) => {
        console.log(`💻 PC joining with session ID: ${sessionId}`);
        if (!sessions.has(sessionId)) {
            sessions.set(sessionId, {
                pcSocketId: socket.id,
                mobileSocketId: null,
                status: 'waiting',
                createdAt: Date.now()
            });
            console.log(`✅ Created new session: ${sessionId}`);
        }
        else {
            const session = sessions.get(sessionId);
            session.pcSocketId = socket.id;
            console.log(`✅ PC reconnected to session: ${sessionId}`);
        }
        socketToSession.set(socket.id, sessionId);
        socket.join(sessionId);
        console.log(`💻 PC connected to session: ${sessionId}`);
    });
    // Mobile joins with session ID
    socket.on('mobile-join', ({ sessionId }) => {
        console.log(`📱 Mobile joining session: ${sessionId}`);
        const session = sessions.get(sessionId);
        if (!session) {
            socket.emit('error', { message: 'Session not found' });
            return;
        }
        session.mobileSocketId = socket.id;
        session.status = 'connected';
        socketToSession.set(socket.id, sessionId);
        socket.join(sessionId);
        // Notify PC
        io.to(session.pcSocketId).emit('mobile-connected');
        socket.emit('session-ready');
        console.log(`✅ Mobile connected to session: ${sessionId}`);
    });
    // Photo captured from mobile
    socket.on('photo-captured', ({ sessionId, imageData }) => {
        console.log(`📸 Photo captured for session: ${sessionId}`);
        const session = sessions.get(sessionId);
        if (!session)
            return;
        // Send to PC
        io.to(session.pcSocketId).emit('photo-received', { imageData });
        console.log(`✅ Photo sent to PC`);
    });
    // Trigger capture from mobile (mobile demande au PC de capturer)
    socket.on('trigger-capture', ({ sessionId }) => {
        console.log(`🎯 Mobile demande capture pour session: ${sessionId}`);
        const session = sessions.get(sessionId);
        if (!session) {
            socket.emit('error', { message: 'Session not found' });
            return;
        }
        // Envoyer le signal au PC pour qu'il capture depuis sa webcam
        io.to(session.pcSocketId).emit('capture-requested');
        console.log(`✅ Signal de capture envoyé au PC`);
    });
    // Disconnect
    socket.on('disconnect', () => {
        console.log(`❌ Client disconnected: ${socket.id}`);
        const sessionId = socketToSession.get(socket.id);
        if (sessionId) {
            const session = sessions.get(sessionId);
            if (session) {
                if (session.pcSocketId === socket.id) {
                    console.log(`💻 PC disconnected from session: ${sessionId}`);
                }
                else if (session.mobileSocketId === socket.id) {
                    console.log(`📱 Mobile disconnected from session: ${sessionId}`);
                    session.mobileSocketId = null;
                    session.status = 'waiting';
                }
            }
            socketToSession.delete(socket.id);
        }
    });
});
// ====================
// START SERVER
// ====================
httpServer.listen(config.port, config.host, () => {
    console.log(`
╔══════════════════════════════════════════════╗
║   FashionistAI TypeScript Backend v2.0       ║
║   🚀 Server running on port ${config.port}            ║
║   🌐 Network IP: http://${config.networkIP}:${config.port}  ║
║   📱 Mobile capture with QR Code enabled     ║
║   🔌 WebSocket ready for real-time comm      ║
║   🐍 Python microservice: ${config.pythonService.url}  ║
╚══════════════════════════════════════════════╝
  `);
});
// Graceful shutdown
process.on('SIGTERM', () => {
    console.log('🛑 SIGTERM received, closing server...');
    httpServer.close(() => {
        console.log('✅ Server closed');
        process.exit(0);
    });
});
//# sourceMappingURL=server.js.map