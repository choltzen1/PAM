# Frontend PR Checklist

- [ ] No inline CSS in templates (`<style>` or `style="..."`)
- [ ] No JS visual inline styling (`style.cssText` or `.style.<prop>` for visuals)
- [ ] No unapproved UI drift (snapshots match baseline)
- [ ] Tracker updated: `docs/UI_REFACTOR_TRACKING.md` and `docs/ui_refactor_tracking.json`
- [ ] Standards followed: `docs/FRONTEND_STANDARDS.md`
- [ ] Tests pass (`pytest` + smoke tests)
