interface Props {
  ok: boolean
  label?: string
}

export default function StatusBadge({ ok, label }: Props) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${
        ok ? 'bg-emerald-900/40 text-emerald-400' : 'bg-red-900/40 text-red-400'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-emerald-400' : 'bg-red-400'}`} />
      {label ?? (ok ? 'OK' : 'FAIL')}
    </span>
  )
}
