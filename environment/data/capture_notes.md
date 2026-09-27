# Localization release incident capture

This directory contains the browser/build evidence from a localization release gate. The audited tab outlived multiple Service Worker and webpack hot-update generations, so a resource being newest at capture end does not mean it was the resource that influenced the audited page.

`audit_context.json`, `sw_events.jsonl`, `request_trace.jsonl`, `initial_cache.json`, `workers.json`, and the captured worker scripts describe browser request/controller state. The worker sources are authoritative for `/diag/` fetch behavior. Cache writes scheduled by `event.waitUntil()` can complete after a response has already been returned.

The audited page also crossed webpack HMR updates while navigating through the six recorded routes. `hmr_session.jsonl` records the navigation, offered update, and route-checkpoint sequence. `hmr_patches.json`, `hmr_snapshots.json`, and `hmr_accept.json` are captured runtime data. `/app/data/hmr_runtime.mjs` is the authoritative source for update acceptance. An accepted update replaces the captured chunk metadata/map variant in that patch and applies its catalog side effects. A reload replaces those HMR-managed values with the named captured reload snapshot. HMR state persists between checkpoints until a reload replaces it.

The same page also uses a mutable import map for localization runtime adapters. `importmap_base.json`, `importmap_patches.json`, `importmap_snapshots.json`, and `module_graph.json` are the captured loader state, while `/app/data/importmap_runtime.mjs` is authoritative for resolution and cache behavior. An HMR patch that is accepted installs its same-id import-map delta; an HMR reload replaces the import-map state with the snapshot whose name is carried by that reload. At each route checkpoint, the route root from `importmap_base.json` is evaluated. A successful `(referrer, specifier)` resolution remains cached for that page lifetime, so later import-map changes do not rewrite an already-resolved module edge; a full reload clears that cache and the set of already-evaluated modules before applying the snapshot preload.

`module_graph.json` records the captured module dependencies, source-module names, and top-level catalog registration effects. A module's catalog effects execute only on its first evaluation in a page lifetime and remain global until a reload. They layer after the normal code-split catalog registrations and the current HMR catalog overlay. The `modules` field for a route checkpoint includes both the webpack source modules and the source modules reachable from that route's import-map root under the loader state actually in effect.

The diagnostic build resources carry webpack metadata, extracted callsites, indexed Source Map v3 files, locale policy, and locale catalog registration events. A route checkpoint uses the chunk/module and map state that existed at that checkpoint. Indexed Source Map v3 state follows the standard cumulative source/original-position rules across generated lines; indexed sections and inline standard source maps remain part of the mapping chain.

Catalog registration is global to the page runtime. The normal code-split registrations from `/diag/catalog/*.jsonl` apply for chunks present at a route checkpoint, and accepted HMR catalog side effects are layered over that state in event order. A removal is a tombstone. Locale aliases, parent fallback, and namespace barriers come from the locale policy resource actually received by the audited tab.

Select/plural arguments with a finite captured `values` set only need branches reachable by those values; otherwise every branch is potentially reachable. Plural and ordinal categories follow the browser runtime's `Intl.PluralRules` for the requested locale. An extracted `integer` is compatible with a numeric ICU requirement.

Produce `/app/output/i18n_contract.json` with exactly `release`, `route_locales`, and `summary`. `release` is the release id of the worker controlling the audited client.

Each route/locale record contains `route`, `locale`, `modules`, `callsites`, and `issues`. `modules` is the sorted source-module set active for that route checkpoint. `callsites` contains the extracted callsites whose fully mapped source module belongs to that set. Each callsite record contains `callsite_id`, `module`, `message`, `source_locale`, `required_args`, and `issues`.

For a resolved message, `source_locale` is the canonical catalog locale that supplied the pattern after alias/fallback processing; it is `null` when unresolved. `required_args` maps argument names to `string`, `number`, or `date`. Ordinary/select arguments are strings, plural/selectordinal and number arguments are numbers, and date/time arguments are dates.

Issue strings are:

- `missing-message:<callsite_id>:<message>`
- `missing-arg:<callsite_id>:<arg>`
- `incompatible-arg:<callsite_id>:<arg>:expected=<type>:actual=<type>`

A route/locale `issues` list is the union of its callsite issues. Ordering is not semantic.

Summary fields:

- `route_locale_count`: number of route/locale records.
- `clean_count`: route/locale records with an empty route-level `issues` list.
- `issue_count`: sum of deduplicated route-level issue-list lengths.
- `callsite_evaluations`: total callsite records across all route/locale records.
