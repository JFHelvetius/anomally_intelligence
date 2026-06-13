interface Props {
  hash: string
  short?: boolean
}

export default function HashChip({ hash, short = true }: Props) {
  const display = short ? `${hash.slice(0, 8)}…${hash.slice(-4)}` : hash
  return (
    <span
      className="font-mono text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded"
      title={hash}
    >
      {display}
    </span>
  )
}
