# AIP Transparency Log Bundle

| Operator | Fingerprint | Exported | Manifests |
|---|---|---|---|
| `jmm-evergreen` | `c8a9c6d4e10c7e644be93108…` | `2026-06-10T02:59:09Z` | 3 (seq 0..2) |

## Qué es esto

Un transparency log firmado del archive AIP. Cada `manifest-NNNNNN.json`
es una snapshot ed25519-firmada del estado del archive en un instante. La
cadena `previous_manifest_hash` ata cada manifest al anterior: manipular
uno viejo invalida todos los posteriores. Cualquier tercero puede verificar
offline usando `public-key.pem` sin necesidad de confiar en el operador
ni acceder al archive original.

## Cómo verificar

**Vía portal web** — abre el AIP Transparency Portal, configura la URL del
bundle apuntando al directorio que contiene este README, y el portal
verificará automáticamente todos los manifests client-side (SHA-256(JCS) +
ed25519).

**Vía CLI** — si tienes los manifests bajo `<archive>/transparency/`:

```
aip transparency verify --chain --archive-root <archive> --public-key public-key.pem
```

## Layout

- `index.json` — metadata del bundle + resúmenes de manifests (entry point)
- `public-key.pem` — clave pública del operador (PEM SubjectPublicKeyInfo)
- `latest.json` — copia del manifest más reciente
- `manifest-NNNNNN.json` — un fichero por secuencia, bytes idénticos al archive

## Trust model

- `public-key.pem` identifica al operador. Su fingerprint SHA-256 del DER
  aparece en cada manifest (`public_key_fingerprint`).
- Si el operador rota su clave, cambia el fingerprint — el portal lo detecta.
- No hay PKI: la identidad real del operador está fuera de este sistema. Lo
  único que se prueba es el vínculo clave-estado.
- No hay TSA: el `signed_at` lo provee el operador. Es operator-supplied.

Generado por `aip transparency export` (Phase 1C).
