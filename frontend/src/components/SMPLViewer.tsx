import React, { useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Stage } from '@react-three/drei';
import * as THREE from 'three';

interface SMPLData {
  vertices: number[][]; // [x, y, z][]
  faces: number[][];    // [v1, v2, v3][]
}

interface SMPLViewerProps {
  meshData: SMPLData;
}

const MeshComponent: React.FC<{ meshData: SMPLData }> = ({ meshData }) => {
  const geometry = useMemo(() => {
    if (!meshData || !meshData.vertices || !meshData.faces) return null;

    const geom = new THREE.BufferGeometry();

    // Convert vertices to Float32Array
    const vertices = new Float32Array(meshData.vertices.flat());
    
    // Convert faces to Uint16Array or Uint32Array (indices)
    const indices = new Uint16Array(meshData.faces.flat());

    geom.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
    geom.setIndex(new THREE.BufferAttribute(indices, 1));
    
    geom.computeVertexNormals();
    
    // Rotate to stand upright (SMPL is often Y-up or Z-up depending on export, 
    // but usually needs 180 deg rot around X to face camera correctly if standard is used)
    // Adjust rotation based on your specific coordinate system match
    geom.rotateX(Math.PI); 

    return geom;
  }, [meshData]);

  if (!geometry) return null;

  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial color="#667eea" roughness={0.5} metalness={0.1} side={THREE.DoubleSide} />
    </mesh>
  );
};

const SMPLViewer: React.FC<SMPLViewerProps> = ({ meshData }) => {
  return (
    <div style={{ width: '100%', height: '400px', background: '#f0f0f0', borderRadius: '8px' }}>
      <Canvas camera={{ position: [0, 0, 2.5], fov: 50 }}>
        <Stage environment="city" intensity={0.6}>
           <MeshComponent meshData={meshData} />
        </Stage>
        <OrbitControls autoRotate={true} autoRotateSpeed={1.0} />
      </Canvas>
    </div>
  );
};

export default SMPLViewer;
