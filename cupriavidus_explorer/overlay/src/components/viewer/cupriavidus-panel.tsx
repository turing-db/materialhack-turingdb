import { type FC, useCallback, useEffect, useRef, useState } from 'react'
import { Icon } from '@blueprintjs/core'
import clsx from 'clsx'

import { useTuringContext } from '@turingcanvas'

import useCypherQuery from '@/hooks/use-cypher-query'
import useGraphEntities from '@/hooks/use-graph-entities'
import { useVisStore } from '@/stores'
import {
  DEFAULT_PRESET,
  LABEL_COLORS,
  LABEL_COLOR_HEX,
  PRESET_GROUPS,
  type Preset,
} from '@/utils/cnecator-presets'

const BASE_COLOR = 0xaaaaaa

export const CupriavidusPanel: FC = () => {
  const cypher = useCypherQuery()
  const { data } = useGraphEntities()
  const turing = useTuringContext()
  const inspecting = useVisStore((state) => state.inspectNodeInfo) !== undefined

  const [collapsed, setCollapsed] = useState(false)
  const [colorByType, setColorByType] = useState(true)
  const [activeQuery, setActiveQuery] = useState<string>(DEFAULT_PRESET.query)

  // Colour every visible node by its primary label.
  const applyColors = useCallback(() => {
    for (const n of turing.instance.nodes) {
      const label = (n.data?.labels ?? [])[0] as string | undefined
      const color = (label && LABEL_COLORS[label]) || BASE_COLOR
      turing.instance.setNodeColor(n, color)
    }
  }, [turing])

  const runPreset = useCallback(
    (preset: Preset) => {
      setActiveQuery(preset.query)
      cypher.mutate(preset.query)
    },
    [cypher]
  )

  // Auto-run the starter view once the canvas instance is ready.
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    let tries = 0
    const tick = () => {
      if (started.current) return
      if (turing.instance && tries++ < 40) {
        started.current = true
        cypher.mutate(DEFAULT_PRESET.query)
      } else if (tries < 40) {
        setTimeout(tick, 250)
      }
    }
    const t = setTimeout(tick, 600)
    return () => clearTimeout(t)
  }, [cypher, turing])

  // Re-apply colouring whenever the rendered graph changes (post-render delay
  // lets the batched canvas add settle first).
  useEffect(() => {
    if (!colorByType) return
    const t = setTimeout(applyColors, 500)
    return () => clearTimeout(t)
  }, [data, colorByType, applyColors])

  // Keep out of the node inspector's way.
  const hidden = inspecting && !collapsed

  if (collapsed || hidden) {
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        className="bg-grey-800 shadow-dark text-content-primary border-grey-600 pointer-events-auto absolute top-0 left-0 z-10 m-4 flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-grey-700"
        title="Open the Cupriavidus necator explorer"
      >
        <Icon icon="lab-test" size={14} />
        <span className="italic">C. necator</span>
        <Icon icon="chevron-right" size={14} />
      </button>
    )
  }

  return (
    <div className="bg-grey-800 shadow-dark border-grey-600 pointer-events-auto absolute top-0 left-0 z-10 flex h-full w-[320px] flex-col overflow-hidden border-r">
      {/* Header */}
      <div className="border-grey-600 flex flex-shrink-0 flex-col gap-1 border-b px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon icon="lab-test" size={16} className="text-content-secondary" />
            <span className="text-content-primary text-sm font-semibold italic">
              Cupriavidus necator H16
            </span>
          </div>
          <button
            type="button"
            onClick={() => setCollapsed(true)}
            className="text-content-tertiary hover:text-content-primary"
            title="Collapse"
          >
            <Icon icon="chevron-left" size={16} />
          </button>
        </div>
        <span className="text-content-tertiary text-xs leading-snug">
          Genome-scale metabolic graph · PHB bioplastics, CO₂ fixation & H₂ oxidation
        </span>
        <span className="text-content-tertiary text-[11px]">
          taxId 381666 · BioModels iCNH2025A · 5,812 nodes / 22,554 edges
        </span>
      </div>

      {/* Colour-by-type toggle + legend */}
      <div className="border-grey-600 flex-shrink-0 border-b px-4 py-3">
        <label className="flex cursor-pointer items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={colorByType}
            onChange={(e) => {
              const on = e.target.checked
              setColorByType(on)
              if (on) applyColors()
              else for (const n of turing.instance.nodes) turing.instance.setNodeColor(n, BASE_COLOR)
            }}
          />
          <span className="text-content-secondary font-medium">Colour nodes by type</span>
        </label>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
          {Object.entries(LABEL_COLOR_HEX).map(([label, hex]) => (
            <span key={label} className="text-content-tertiary flex items-center gap-1 text-[11px]">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: hex }}
              />
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Preset groups */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-2">
        {PRESET_GROUPS.map((group) => (
          <div key={group.title} className="mb-3">
            <div className="text-content-tertiary mb-1 flex items-center gap-1.5 px-1 text-[11px] font-semibold tracking-wide uppercase">
              <Icon icon={group.icon as never} size={12} />
              {group.title}
            </div>
            <div className="flex flex-col gap-1">
              {group.presets.map((preset) => {
                const active = activeQuery === preset.query
                return (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => runPreset(preset)}
                    title={preset.hint}
                    className={clsx(
                      'group flex flex-col items-start rounded-md border px-2.5 py-1.5 text-left transition-colors',
                      active
                        ? 'border-grey-500 bg-grey-700'
                        : 'border-transparent hover:border-grey-600 hover:bg-grey-700/50'
                    )}
                  >
                    <span className="text-content-primary text-xs font-medium">{preset.label}</span>
                    <span className="text-content-tertiary line-clamp-2 text-[11px] leading-tight">
                      {preset.hint}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="border-grey-600 text-content-tertiary flex-shrink-0 border-t px-4 py-2 text-[11px]">
        Tip: double-click a node to expand its neighbours · click for details
      </div>
    </div>
  )
}

export default CupriavidusPanel
