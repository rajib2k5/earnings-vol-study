import { useEffect, useState } from 'react'
import { tokenColour, type Rgb } from '../lib/terrain'

/** Used if a theme token cannot be read: the dark-theme values of --teal and --accent from index.css. */
const FALLBACK_LOW = '#4fb8a8'
const FALLBACK_HIGH = '#e0a458'

export interface TokenColours {
  low: Rgb
  high: Rgb
}

function readColours(): TokenColours {
  const styles = getComputedStyle(document.documentElement)
  const read = (name: string) => styles.getPropertyValue(name)
  return { low: tokenColour(read, '--teal', FALLBACK_LOW), high: tokenColour(read, '--accent', FALLBACK_HIGH) }
}

/**
 * The terrain's low/high colours, taken from the app's theme tokens so the 3D view matches the
 * rest of the page. Re-read whenever the theme toggle changes <html data-theme>.
 */
export function useTokenColours(): TokenColours {
  const [colours, setColours] = useState(readColours)
  useEffect(() => {
    const observer = new MutationObserver(() => setColours(readColours()))
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])
  return colours
}
