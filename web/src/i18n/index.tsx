/**
 * Minimal in-house i18n.
 *
 * Why custom and not react-i18next? At the scale of this project (two
 * languages, ~200 strings, mostly static dictionaries) the heavyweight
 * solutions add bundle size and ceremony without payoff. This file is
 * ~50 lines of TypeScript, type-safe via the `Lang` union, and shares
 * the persistent setting via `localStorage`.
 *
 * Audience split:
 *   - "operator" UI: technical, uses crypto/PKI vocabulary.
 *   - "recipient" UI: non-technical, avoids jargon.
 *
 * Both share the same dictionary; the audience adjustment lives in
 * component props, not in the dictionary, to keep keys flat.
 */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import en from './en'
import esES from './es-ES'

export type Lang = 'en' | 'es-ES'

const DICTIONARIES: Record<Lang, typeof en> = {
  'en': en,
  'es-ES': esES,
}

const LANG_LABEL: Record<Lang, string> = {
  'en': 'English',
  'es-ES': 'Español (España)',
}

const STORAGE_KEY = 'aip.lang'
const DEFAULT_LANG: Lang = 'en'

// ─── Context ──────────────────────────────────────────────────────────────

interface I18nContextValue {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: keyof typeof en, fallback?: string) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    if (typeof window === 'undefined') return DEFAULT_LANG
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return (stored === 'en' || stored === 'es-ES') ? stored : DEFAULT_LANG
  })

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, lang)
      document.documentElement.lang = lang
    }
  }, [lang])

  const setLang = (l: Lang) => setLangState(l)

  const value = useMemo<I18nContextValue>(() => {
    const dict = DICTIONARIES[lang]
    return {
      lang,
      setLang,
      t: (key, fallback) => {
        const v = dict[key]
        if (typeof v === 'string') return v
        // Defensive: missing key falls back to the EN value, then to the
        // explicit fallback, then to the key itself (visible in dev).
        const enValue = en[key]
        if (typeof enValue === 'string') return enValue
        return fallback ?? String(key)
      },
    }
  }, [lang])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext)
  if (!ctx) {
    throw new Error('useI18n() called outside of <I18nProvider>')
  }
  return ctx
}

// Convenience: just the translator.
export function useT() {
  return useI18n().t
}

// ─── Language switcher ────────────────────────────────────────────────────

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { lang, setLang } = useI18n()
  const next: Lang = lang === 'en' ? 'es-ES' : 'en'
  return (
    <button
      type="button"
      onClick={() => setLang(next)}
      className="inline-flex items-center gap-1.5 font-mono uppercase tracking-wider transition-colors"
      style={{
        color: 'var(--muted2)',
        fontSize: compact ? '10px' : '11px',
        cursor: 'pointer',
      }}
      title={`Switch to ${LANG_LABEL[next]}`}
    >
      <span style={{ opacity: 0.7 }}>{compact ? lang : LANG_LABEL[lang]}</span>
      <span style={{ opacity: 0.4 }}>→</span>
      <span>{compact ? next : LANG_LABEL[next]}</span>
    </button>
  )
}
