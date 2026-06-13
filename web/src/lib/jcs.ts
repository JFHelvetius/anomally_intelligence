/**
 * JCS (RFC 8785) canonicalization — subset matching `aip/core/hashing.py`.
 *
 * Supported types:
 *   null, boolean, integer (Number with no fractional part), string,
 *   array of supported, object with string keys
 *
 * Rejected: float (Number with decimals), bigint, undefined, symbol, others.
 *
 * Key sort: by UTF-16 code units. JavaScript string comparison uses code-unit
 * order natively — identical to Python's `key.encode("utf-16-be")` ordering
 * for both BMP and supplementary code points (surrogate pairs sort identically
 * to their UTF-16-BE byte sequence).
 *
 * Output: UTF-8 bytes, no insignificant whitespace, control chars escaped
 * with `\uXXXX`, RFC 8259 §7 mandatory short escapes for \b \f \n \r \t.
 */

export type JCSValue =
  | null
  | boolean
  | number
  | string
  | JCSValue[]
  | { [key: string]: JCSValue }

const SHORT_ESCAPES: Record<string, string> = {
  '\b': '\\b',
  '\f': '\\f',
  '\n': '\\n',
  '\r': '\\r',
  '\t': '\\t',
}

function emitString(value: string, out: string[]): void {
  out.push('"')
  for (const ch of value) {
    const cp = ch.codePointAt(0)!
    if (ch === '"') {
      out.push('\\"')
    } else if (ch === '\\') {
      out.push('\\\\')
    } else if (cp < 0x20) {
      const short = SHORT_ESCAPES[ch]
      if (short !== undefined) {
        out.push(short)
      } else {
        out.push('\\u' + cp.toString(16).padStart(4, '0'))
      }
    } else {
      out.push(ch)
    }
  }
  out.push('"')
}

function serialize(value: JCSValue, out: string[]): void {
  if (value === null) {
    out.push('null')
    return
  }
  if (value === true) {
    out.push('true')
    return
  }
  if (value === false) {
    out.push('false')
    return
  }
  if (typeof value === 'number') {
    if (!Number.isInteger(value)) {
      throw new TypeError('JCS subset rejects non-integer numbers (float)')
    }
    out.push(value.toString())
    return
  }
  if (typeof value === 'string') {
    emitString(value, out)
    return
  }
  if (Array.isArray(value)) {
    out.push('[')
    for (let i = 0; i < value.length; i++) {
      if (i > 0) out.push(',')
      serialize(value[i], out)
    }
    out.push(']')
    return
  }
  if (typeof value === 'object') {
    // Sort keys by UTF-16 code-unit order (matches Python's utf-16-be sort).
    const keys = Object.keys(value).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0))
    out.push('{')
    let first = true
    for (const k of keys) {
      if (!first) out.push(',')
      emitString(k, out)
      out.push(':')
      serialize(value[k], out)
      first = false
    }
    out.push('}')
    return
  }
  throw new TypeError(`unsupported type for JCS: ${typeof value}`)
}

export function jcsCanonicalize(value: JCSValue): Uint8Array {
  const parts: string[] = []
  serialize(value, parts)
  return new TextEncoder().encode(parts.join(''))
}

/** SHA-256 of arbitrary bytes, hex-encoded lowercase. */
export async function sha256Hex(data: Uint8Array): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-256', data as BufferSource)
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
}
