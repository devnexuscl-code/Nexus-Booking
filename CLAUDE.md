# Nexus Booking — PRODUCCIÓN

SaaS multi-tenant de agendamiento (estilo Calendly) para profesionales
independientes con links de reserva propios. Stack: **React + Vite +
TypeScript + Supabase** (Postgres + Auth + Edge Functions). CSS propio
(sin Bootstrap/MUI), tipografía Space Grotesk + Inter, tema oscuro por
defecto. Deploy en **Cloudflare Pages** (auto-deploy desde GitHub),
dominio **nexusdev.cl**.

## Este ambiente
- **⚠️ Ambiente: PRODUCCIÓN.** Todo cambio de BD afecta datos y clientes
  reales. El MCP de Supabase de esta carpeta debería estar en
  **`read_only`** por defecto; para aplicar migraciones hay que habilitarlo
  conscientemente. **Nunca apliques DDL en PROD sin haberlo probado y
  verificado antes en QA.**
- Supabase `project_ref`: `mkbsfmoknsbhbskayrgg`
- Repo GitHub: `devnexuscl-code/Nexus-Booking` (organización nexusdev.cl)
- Correo transaccional: Brevo vía `mail.nexusdev.cl` (DKIM/SPF/DMARC ok).
- **Regla de oro:** definir cada cambio de BD una vez y aplicarlo a QA y
  PROD en la misma tanda. Nunca dejar los ambientes divergentes.
- Nota: los `slug` de empresa en PROD son hashes (no legibles como en QA).

## Arquitectura multi-tenant (crítico)
- Varias empresas comparten la misma BD; el aislamiento es por **RLS**.
- Dos flujos: **backoffice autenticado** y **reserva pública anónima**
  (sin login).
- El tenant del backoffice sale de `auth.uid()` vía la función
  `usuario_tiene_rol(id_empresa, roles[])`. El tenant público se resuelve
  con la RPC SECURITY DEFINER `resolver_tenant_publico(slug)`.
  **Nunca** por una variable de sesión de Postgres.
- Roles: `admin`, `supervisor`, `recepcionista`, `agenda_operador`, `prestador`.
- Tablas núcleo: empresas, sucursales, prestadores, servicios, categorias,
  tipo_categorias, clientes, agendamientos, prestador_horarios,
  prestador_ausencias, prestador_servicios, dias_bloqueados, usuario_roles, roles.

## Invariantes de seguridad — NO romper
- Toda política RLS filtra por `id_empresa` vía `usuario_tiene_rol(...)` o
  `auth.uid()`. **Nunca** por `current_setting`/`set_config` (se "pega"
  entre requests por el pooling de Supavisor).
- Toda función **SECURITY DEFINER** que reciba un id (id_prestador,
  id_empresa, etc.) **debe validar el tenant internamente** (p.ej.
  `usuario_tiene_rol` sobre la empresa del recurso) antes de devolver o
  modificar datos. No confiar en el id que manda el front.
- `anon` solo lee catálogo público NO sensible y **a través de vistas
  seguras**: `v_servicios_publico` (sin `comision`/`tipo_comision`),
  `v_prestadores_publico` (sin email/teléfono), `v_sucursales_publico`.
  `anon` **no** tiene SELECT sobre las tablas `servicios`, `empresas` ni
  `agendamientos`.
- PII de cliente (nombre/teléfono/email/rut) y `token_cancelacion`: nunca
  exponer a `anon` ni cross-tenant.
- Funciones con secretos (`get_correo_config`, `desencriptar_valor`,
  `generar_token_recovery`): EXECUTE revocado de anon/authenticated (solo
  service_role / edge functions).
- Doble-reserva: la protege la constraint EXCLUDE `no_solapamiento_prestador`
  (por `id_prestador`).

## Convenciones frontend
- Filtro empresa/sucursal: hook `useFiltroEmpresa` (devuelve primitivos y
  setters) + componente `SelectorFiltro`. No hacer un hook que devuelva JSX
  (causaba re-mounts).
- CRUD genérico: `crudFactory` + `CrudPage` (config por campos). Selects
  dependientes de otro campo: `dependsOn` + `opcionesDe`.
- Lecturas públicas en `services/entityServices.ts`
  (`listServiciosPublico` → `v_servicios_publico`, etc.).
- Disponibilidad en `disponibilidad.ts` (granularidad interna 5 min vs
  granularidad de display; columnas por prestador: `paso_agenda`,
  `buffer_min`, `dias_agenda`).

## Deploy / gotchas
- `npm run build` = `tsc -b && vite build`. Requiere env vars
  `VITE_APP_ENV`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.
- SPA routing con `public/_redirects` (`/* /index.html 200`) + `404.html`.
- Cloudflare auto-deploya al hacer push. Si un cambio no aparece en prod,
  casi siempre es que el archivo no quedó en el commit.
- Secretos (`.env`, tokens, scripts `subir*.py`) fuera del repo (`.gitignore`).

## MCP Supabase
- Esta carpeta apunta al `project_ref` `mkbsfmoknsbhbskayrgg` (PROD).
- **Preferir `read_only`.** Migraciones vía `apply_migration` solo cuando
  vayas a aplicar conscientemente; consultas/verificación vía `execute_sql`.
