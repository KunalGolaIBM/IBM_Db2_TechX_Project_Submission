export interface Opening {
  eco: string
  name: string
  moves: string
}

// A highly simplified subset of common openings by sequence of moves
// For a production app, this would be a much larger dictionary or fetched via an API.
const OPENINGS: Opening[] = [
  { eco: 'C20', name: 'King\'s Pawn Game', moves: 'e4 e5' },
  { eco: 'C44', name: 'King\'s Pawn Game: King\'s Knight Opening', moves: 'e4 e5 Nf3' },
  { eco: 'C50', name: 'Italian Game', moves: 'e4 e5 Nf3 Nc6 Bc4' },
  { eco: 'C53', name: 'Italian Game: Giuoco Pianissimo', moves: 'e4 e5 Nf3 Nc6 Bc4 Bc5 c3' },
  { eco: 'C55', name: 'Two Knights Defense', moves: 'e4 e5 Nf3 Nc6 Bc4 Nf6' },
  { eco: 'C60', name: 'Ruy Lopez', moves: 'e4 e5 Nf3 Nc6 Bb5' },
  { eco: 'C68', name: 'Ruy Lopez: Exchange Variation', moves: 'e4 e5 Nf3 Nc6 Bb5 a6 Bxc6' },
  { eco: 'B00', name: 'King\'s Pawn Game', moves: 'e4' },
  { eco: 'B01', name: 'Scandinavian Defense', moves: 'e4 d5' },
  { eco: 'B10', name: 'Caro-Kann Defense', moves: 'e4 c6' },
  { eco: 'B20', name: 'Sicilian Defense', moves: 'e4 c5' },
  { eco: 'B30', name: 'Sicilian Defense: Old Sicilian', moves: 'e4 c5 Nf3 Nc6' },
  { eco: 'B90', name: 'Sicilian Defense: Najdorf Variation', moves: 'e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6' },
  { eco: 'C00', name: 'French Defense', moves: 'e4 e6' },
  { eco: 'D00', name: 'Queen\'s Pawn Game', moves: 'd4' },
  { eco: 'D02', name: 'Queen\'s Pawn Game: London System', moves: 'd4 d5 Nf3 Nf6 Bf4' },
  { eco: 'D06', name: 'Queen\'s Gambit', moves: 'd4 d5 c4' },
  { eco: 'D20', name: 'Queen\'s Gambit Accepted', moves: 'd4 d5 c4 dxc4' },
  { eco: 'D30', name: 'Queen\'s Gambit Declined', moves: 'd4 d5 c4 e6' },
  { eco: 'E00', name: 'Queen\'s Pawn Game: Catalan Opening', moves: 'd4 Nf6 c4 e6 g3' },
  { eco: 'E60', name: 'King\'s Indian Defense', moves: 'd4 Nf6 c4 g6' },
  { eco: 'E90', name: 'King\'s Indian Defense', moves: 'd4 Nf6 c4 g6 Nc3 Bg7 e4 d6' },
  { eco: 'A00', name: 'Irregular Opening', moves: '' }
]

export function getOpeningName(history: string[]): string {
  return getOpening(history).name
}

export function getOpening(history: string[]): Opening {
  // Try to match the longest sequence of moves
  for (let i = history.length; i > 0; i--) {
    const sequence = history.slice(0, i).join(' ')
    const match = OPENINGS.find(o => o.moves === sequence)
    if (match) return match
  }
  return history.length > 0
    ? OPENINGS[OPENINGS.length - 1]
    : { eco: 'START', name: 'Starting Position', moves: '' }
}
