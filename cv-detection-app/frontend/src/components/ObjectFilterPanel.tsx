import React from 'react'

export default function ObjectFilterPanel({ classes = [], onToggle = () => {} }: { classes?: string[]; onToggle?: (c: string, on: boolean) => void }) {
  return (
    <div>
      <h3 className="font-semibold">Filters</h3>
      {classes.map(c => (
        <label key={c} className="block">
          <input type="checkbox" defaultChecked onChange={e => onToggle(c, e.target.checked)} /> {c}
        </label>
      ))}
    </div>
  )
}
