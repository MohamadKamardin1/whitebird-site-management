# Integrated Frontend Delivery Todo

- [x] Merge the White Bird Zanzibar frontend source into this Django repository under a dedicated frontend directory, retaining the frontend documentation, task backlog, and project configuration.
- [x] Add documented local-development routing so the frontend can call the Django Ninja API at `/api/site-management/v1` without an external deployment dependency.
- [x] Install and validate frontend dependencies within the integrated repository without modifying existing Django API contracts.
- [x] Run Django checks, frontend type checks, frontend production build, and HTTP smoke tests against the locally running combined services.
- [x] Verify the Git worktree, commit the integrated frontend change set with the configured author identity, and push the commit to the repository’s configured GitHub remote.
