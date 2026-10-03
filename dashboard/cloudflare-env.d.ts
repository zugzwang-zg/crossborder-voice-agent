// The database remains opt-in; getDb() checks that the binding is configured.
declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
  }
}
