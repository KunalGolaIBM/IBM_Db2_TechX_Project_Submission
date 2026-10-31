let context: AudioContext | null = null
let master: GainNode | null = null
let active = false

export async function startAmbient() {
  if (active) {
    await context?.resume()
    return
  }
  context = new AudioContext()
  master = context.createGain()
  master.gain.value = 0.0001
  master.connect(context.destination)

  const frequencies = [55, 82.41, 110, 164.81]
  frequencies.forEach((frequency, index) => {
    const oscillator = context!.createOscillator()
    const gain = context!.createGain()
    const filter = context!.createBiquadFilter()
    oscillator.type = index % 2 ? 'sine' : 'triangle'
    oscillator.frequency.value = frequency
    oscillator.detune.value = index * 3 - 4
    gain.gain.value = 0.022 / (index + 1)
    filter.type = 'lowpass'
    filter.frequency.value = 380 + index * 90
    oscillator.connect(filter).connect(gain).connect(master!)
    oscillator.start()
  })

  const lfo = context.createOscillator()
  const lfoGain = context.createGain()
  lfo.frequency.value = 0.055
  lfoGain.gain.value = 0.012
  lfo.connect(lfoGain).connect(master.gain)
  lfo.start()
  master.gain.exponentialRampToValueAtTime(0.18, context.currentTime + 2.5)
  active = true
}

export function setAmbientMuted(muted: boolean) {
  if (!context || !master) return
  master.gain.cancelScheduledValues(context.currentTime)
  master.gain.setTargetAtTime(muted ? 0.0001 : 0.18, context.currentTime, 0.2)
}

export function playMoveTone(capture = false) {
  if (!context || !master) return
  const oscillator = context.createOscillator()
  const gain = context.createGain()
  
  if (capture) {
    oscillator.type = 'square'
    const filter = context.createBiquadFilter()
    filter.type = 'lowpass'
    filter.frequency.setValueAtTime(800, context.currentTime)
    filter.frequency.exponentialRampToValueAtTime(100, context.currentTime + 0.2)
    oscillator.frequency.setValueAtTime(130.81, context.currentTime)
    oscillator.frequency.exponentialRampToValueAtTime(65.41, context.currentTime + 0.18)
    gain.gain.setValueAtTime(0.05, context.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.3)
    oscillator.connect(filter).connect(gain).connect(master)
  } else {
    oscillator.type = 'sine'
    oscillator.frequency.setValueAtTime(196, context.currentTime)
    oscillator.frequency.exponentialRampToValueAtTime(246.94, context.currentTime + 0.18)
    gain.gain.setValueAtTime(0.07, context.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.45)
    oscillator.connect(gain).connect(master)
  }
  
  oscillator.start()
  oscillator.stop(context.currentTime + 0.5)
}

export function playCheckTone() {
  if (!context || !master) return
  const oscillator = context.createOscillator()
  const gain = context.createGain()
  oscillator.type = 'triangle'
  oscillator.frequency.setValueAtTime(329.63, context.currentTime) // E4
  oscillator.frequency.exponentialRampToValueAtTime(440.00, context.currentTime + 0.1) // A4
  gain.gain.setValueAtTime(0.0, context.currentTime)
  gain.gain.linearRampToValueAtTime(0.08, context.currentTime + 0.05)
  gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.6)
  oscillator.connect(gain).connect(master)
  oscillator.start()
  oscillator.stop(context.currentTime + 0.7)
}

export function playGameOverTone(victory: boolean) {
  const ctx = context
  const mst = master
  if (!ctx || !mst) return
  
  const frequencies = victory ? [261.63, 329.63, 392.00, 523.25] : [261.63, 246.94, 220.00, 196.00]
  frequencies.forEach((freq, i) => {
    const oscillator = ctx.createOscillator()
    const gain = ctx.createGain()
    oscillator.type = victory ? 'sine' : 'sawtooth'
    oscillator.frequency.setValueAtTime(freq, ctx.currentTime + i * 0.15)
    gain.gain.setValueAtTime(0, ctx.currentTime)
    gain.gain.setValueAtTime(0.06, ctx.currentTime + i * 0.15)
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + i * 0.15 + 1.5)
    
    const filter = ctx.createBiquadFilter()
    filter.type = 'lowpass'
    filter.frequency.value = victory ? 1200 : 400
    
    oscillator.connect(filter).connect(gain).connect(mst)
    oscillator.start(ctx.currentTime + i * 0.15)
    oscillator.stop(ctx.currentTime + i * 0.15 + 2)
  })
}
