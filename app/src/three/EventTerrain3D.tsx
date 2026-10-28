/**
 * 3D surface of IV by company (z) and event day (x), drawn with react-three-fiber.
 * At milestone 0 the values are ILLUSTRATIVE synthetic numbers from the seeded RNG, labelled as such.
 * All the maths lives in src/lib (terrain.ts, illustrative.ts, motion.ts); this file only wires it to WebGL.
 * It is loaded with React.lazy (see ThreeDPreview) so first paint and tests do not need WebGL.
 */
import { useEffect, useMemo, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { BufferAttribute, BufferGeometry, DoubleSide } from 'three'
import { ILLUSTRATIVE_LABEL, illustrativeIvGrid } from '../lib/illustrative'
import { controlsConfig, prefersReducedMotion, type ControlsConfig } from '../lib/motion'
import { gridToTerrain, type Terrain } from '../lib/terrain'
import { useTokenColours } from './useTokenColours'

const DEFAULT_SEED = 2026

function TerrainScene({ terrain, config }: { terrain: Terrain; config: ControlsConfig }) {
  const geometry = useMemo(() => {
    const g = new BufferGeometry()
    g.setAttribute('position', new BufferAttribute(terrain.positions, 3))
    g.setAttribute('color', new BufferAttribute(terrain.colors, 3))
    g.setIndex(new BufferAttribute(terrain.indices, 1))
    g.computeVertexNormals()
    return g
  }, [terrain])
  useEffect(() => () => geometry.dispose(), [geometry])

  return (
    <>
      <ambientLight intensity={0.9} />
      <directionalLight position={[6, 10, 4]} intensity={1.4} />
      <mesh geometry={geometry}>
        <meshStandardMaterial vertexColors side={DoubleSide} />
      </mesh>
      <OrbitControls
        autoRotate={config.autoRotate}
        autoRotateSpeed={config.autoRotateSpeed}
        enableDamping={config.enableDamping}
        target={[0, 1, 0]}
      />
    </>
  )
}

export default function EventTerrain3D({ seed = DEFAULT_SEED }: { seed?: number }) {
  const [config] = useState(() => controlsConfig(prefersReducedMotion()))
  const { low, high } = useTokenColours()
  const terrain = useMemo(() => gridToTerrain(illustrativeIvGrid(seed), { low, high }), [seed, low, high])

  return (
    <figure className="terrain">
      <div className="terrain-canvas">
        <Canvas frameloop={config.frameloop} camera={{ position: [9, 7, 9], fov: 45 }} dpr={[1, 2]}>
          <TerrainScene terrain={terrain} config={config} />
        </Canvas>
      </div>
      <figcaption>
        <span className="terrain-label">{ILLUSTRATIVE_LABEL}</span>
        <span className="sub">x: event day (-10 to +10) · z: company · height and colour: implied volatility. Drag to orbit, scroll to zoom.</span>
      </figcaption>
    </figure>
  )
}
