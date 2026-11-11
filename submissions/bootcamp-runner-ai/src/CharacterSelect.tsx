import { useState } from 'react'
import { Check, Lock, Sparkles } from 'lucide-react'
import { CharacterPreview } from './CharacterPreview'
import { characters } from './data'
import { unlockCharacter } from './progression'
import type { PlayerProgress } from './types'

interface Props {
  progress: PlayerProgress
  onChange: (next: PlayerProgress) => void
}

/**
 * Character selection screen.
 *
 * Layout is a two-column grid on wide screens and a single column on narrow
 * ones, so the preview always gets its own box and the information / unlock
 * controls never sit on top of the model.
 */
export function CharacterSelect({ progress, onChange }: Props) {
  const [previewId, setPreviewId] = useState(progress.selectedCharacter)
  const preview = characters.find((item) => item.id === previewId) ?? characters[0]
  const [angle, setAngle] = useState(0)
  const unlocked = progress.unlockedCharacters.includes(preview.id)
  const selected = progress.selectedCharacter === preview.id
  const affordable = progress.totalCoins >= preview.unlockCost

  return (
    <div className="character-select">
      <div className="preview-column">
        <CharacterPreview key={preview.id} character={preview} onAngleChange={setAngle} />
        <p className="preview-readout" aria-live="polite">
          <span>{preview.name}</span>
          <span>{angle}°</span>
        </p>
      </div>

      <div className="info-column">
        <div className="info-card">
          <span className="eyebrow">
            <Sparkles size={13} /> {unlocked ? 'UNLOCKED RUNNER' : 'LOCKED RUNNER'}
          </span>
          <h2>{preview.name}</h2>
          <p className="role">{preview.role}</p>
          <p className="effect">{preview.effect}</p>
          <div className="info-actions">
            {unlocked ? (
              <button
                className="primary-button"
                disabled={selected}
                onClick={() => onChange({ ...progress, selectedCharacter: preview.id })}
              >
                {selected ? <><Check size={17} /> Selected</> : 'Select runner'}
              </button>
            ) : (
              <button
                className="primary-button"
                disabled={!affordable}
                onClick={() => onChange(unlockCharacter(progress, preview.id))}
              >
                <Lock size={16} /> Unlock · {preview.unlockCost} coins
              </button>
            )}
            {!unlocked && !affordable && (
              <small className="muted">You have {progress.totalCoins} coins. Keep running to earn more.</small>
            )}
          </div>
        </div>

        <div className="roster" role="list" aria-label="Roster">
          {characters.map((item) => {
            const isUnlocked = progress.unlockedCharacters.includes(item.id)
            return (
              <button
                key={item.id}
                type="button"
                role="listitem"
                className={`roster-item ${item.id === preview.id ? 'active' : ''} ${isUnlocked ? '' : 'locked'}`}
                onClick={() => setPreviewId(item.id)}
                aria-pressed={item.id === preview.id}
              >
                <span className="roster-swatch" style={{ background: `linear-gradient(145deg, ${item.color}, ${item.accent})` }} />
                <span className="roster-text">
                  <strong>{item.name}</strong>
                  <small>{isUnlocked ? (progress.selectedCharacter === item.id ? 'Selected' : 'Unlocked') : `${item.unlockCost} coins`}</small>
                </span>
                {!isUnlocked && <Lock size={13} />}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
