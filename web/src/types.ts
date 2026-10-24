export type Scalar = string | number | boolean | null
export type OptionValue = Scalar | Exclude<Scalar, null>[]
export type Options = Record<string, OptionValue>
export type OptionDraft = Record<string, string | boolean>

export interface Schema {
  type?: string
  title?: string
  description?: string
  default?: OptionValue
  enum?: Scalar[]
  properties?: Record<string, Schema>
  required?: string[]
  items?: Schema
  $ref?: string
  $defs?: Record<string, Schema>
  anyOf?: Schema[]
  nullable?: boolean
  minimum?: number
  maximum?: number
  minLength?: number
  maxLength?: number
  pattern?: string
}
export interface PluginSettings {
  enabled: boolean
  load_on_start: boolean
  group_ids: string[]
  group_user_ids: Record<string, string[]>
  allow_private: boolean
  private_user_ids: string[] | null
  options: Options
  group_options: Record<string, Options>
}
export interface Plugin {
  id: string
  name: string
  description: string
  commands: string[]
  settings: PluginSettings
  loaded: boolean
  load_error: string | null
  load_state: 'failed' | 'loaded' | 'not_loaded'
  restart_required: boolean
  options_schema: Schema
}
export interface Status {
  started_at: string
  connected_accounts: string[]
  coolify_url: string
  process_restart_supported: boolean
}
export interface AlbumImage {
  id: string
  album: string
  format: string
  size: number
  created_at: string
  source: string
  metadata: { group_id?: string }
  url: string
}
export interface GroupDraft {
  key: number
  id: string
  memberMode: 'all' | 'allowlist'
  users: string
  options: OptionDraft
  original: Options
}
export interface PluginDraft {
  enabled: boolean
  load_on_start: boolean
  groups: GroupDraft[]
  privateMode: 'off' | 'all' | 'allowlist'
  privateUsers: string
  options: OptionDraft
}
