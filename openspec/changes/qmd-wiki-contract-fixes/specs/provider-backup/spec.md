## ADDED Requirements

### Requirement: Provider declares backup paths
The provider SHALL implement `backup_paths()` returning the absolute resolved wiki
directories so `hermes backup`/`import` capture knowledge stored outside HERMES_HOME. It
SHALL work without `initialize()` and without network access.

#### Scenario: Wiki dirs declared for backup
- **WHEN** `backup_paths()` is called on an uninitialized provider with a valid config
- **THEN** it returns the resolved `wiki_dirs` that exist on disk