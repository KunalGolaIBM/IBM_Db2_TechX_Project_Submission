import React, { useRef, useState } from 'react';
import { Pencil } from 'lucide-react';

interface CustomMoodInputProps {
  value: string;
  onChange: (val: string) => void;
}

const MAX = 200;

const CustomMoodInput: React.FC<CustomMoodInputProps> = ({ value, onChange }) => {
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (e.target.value.length <= MAX) {
      onChange(e.target.value);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        background: 'rgba(10,8,30,0.6)',
        border: focused
          ? '1px solid rgba(168,85,247,0.7)'
          : '1px solid rgba(255,255,255,0.12)',
        borderRadius: '0.75rem',
        padding: '10px 14px',
        boxShadow: focused ? '0 0 0 3px rgba(168,85,247,0.18)' : 'none',
        transition: 'border 0.2s, box-shadow 0.2s',
        cursor: 'text',
      }}
      onClick={() => textareaRef.current?.focus()}
    >
      {/* Pencil icon */}
      <Pencil
        size={16}
        style={{
          color: focused ? 'rgba(168,85,247,0.9)' : 'rgba(255,255,255,0.3)',
          marginTop: 3,
          flexShrink: 0,
          transition: 'color 0.2s',
        }}
      />

      {/* Textarea + char count column */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="Describe your mood in your own words… (optional)"
          rows={2}
          maxLength={MAX}
          style={{
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#fff',
            fontSize: '0.82rem',
            lineHeight: 1.5,
            resize: 'none',
            width: '100%',
            fontFamily: 'inherit',
          }}
        />
        {/* Char count */}
        <span
          style={{
            alignSelf: 'flex-end',
            fontSize: '0.68rem',
            color:
              value.length >= MAX
                ? 'rgba(248,113,113,0.8)'
                : 'rgba(255,255,255,0.3)',
          }}
        >
          {value.length}/{MAX}
        </span>
      </div>
    </div>
  );
};

export default CustomMoodInput;
