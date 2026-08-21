# Changelog

## [0.5.11](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.5.10...v0.5.11) (2026-08-21)


### Bug Fixes

* **lib:** rule 3 must walk up to the primary checkout ([512a1c2](https://github.com/thewoolleyman/livespec-driver-claude/commit/512a1c2eb36f51de525138c657e598ab1c578e62))

## [0.5.10](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.5.9...v0.5.10) (2026-08-21)


### Bug Fixes

* **lib:** rule 2 must identify livespec core, not any repo shipping prose/ ([515a7c8](https://github.com/thewoolleyman/livespec-driver-claude/commit/515a7c84b66647b2de25c135313030d160fcac24))
* **skills:** the post-resolve guard must identify core, not a prose dir ([a41ee99](https://github.com/thewoolleyman/livespec-driver-claude/commit/a41ee993eaeb0c2726e6c687deb3b2ed607e974e))


### Refactoring

* **lib:** extract core-root operator text to a sibling module ([225adff](https://github.com/thewoolleyman/livespec-driver-claude/commit/225adff1d92a7de388f3384ea5e4374ff81917e7))

## [0.5.9](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.5.8...v0.5.9) (2026-08-20)


### Bug Fixes

* **skill:** carry --only-topic in the revise invocation forms ([4eb563b](https://github.com/thewoolleyman/livespec-driver-claude/commit/4eb563ba746a1b6f65a7662b12d9c0c166d214c3))

## [0.5.8](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.5.7...v0.5.8) (2026-08-19)


### Bug Fixes

* require shell command position for rate-limit guard loop keywords ([08fd2d1](https://github.com/thewoolleyman/livespec-driver-claude/commit/08fd2d1de8a8afab9ba5137963a45e8ec2c7325f))

## [0.5.7](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.5.6...v0.5.7) (2026-08-17)


### Bug Fixes

* **ci:** make export-ci-telemetry.sh ARG_MAX-safe ([5ed9878](https://github.com/thewoolleyman/livespec-driver-claude/commit/5ed9878eb81fa8625dfea6a65a9763a3f1d07275))

## [0.5.6](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.5.5...v0.5.6) (2026-08-17)


### Bug Fixes

* **check:** coverage dedup hardening — clean-env producer + consume-once consumer ([f362e6a](https://github.com/thewoolleyman/livespec-driver-claude/commit/f362e6a19c1b178f0c6dba29140df32b69c7807a))

## [0.5.5](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.5.4...v0.5.5) (2026-08-14)


### Bug Fixes

* narrow github rate-limit select matcher ([1f565cf](https://github.com/thewoolleyman/livespec-driver-claude/commit/1f565cf7b99073528f89c01757743ac1ed7a6e9d))

## [0.5.4](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.5.3...v0.5.4) (2026-08-13)


### Bug Fixes

* **ci:** unshallow self-hosted checkout so origin/master..HEAD ranges resolve ([6d82bbc](https://github.com/thewoolleyman/livespec-driver-claude/commit/6d82bbc658b62585c639946955427fad529e8097))

## [0.5.3](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.5.2...v0.5.3) (2026-08-13)


### Bug Fixes

* **ci:** add MISE_HTTP_RETRIES alongside UV_HTTP_RETRIES ([751b297](https://github.com/thewoolleyman/livespec-driver-claude/commit/751b2971a5b107bf0fb8a8d83630bd004fb411f2))

## [0.5.2](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.5.1...v0.5.2) (2026-08-06)


### Bug Fixes

* **ci:** resolve livespec as a sibling clone in check-doctor-static ([dc1c9c7](https://github.com/thewoolleyman/livespec-driver-claude/commit/dc1c9c776138fe8055acb1b2968aba6060470b06))

## [0.5.1](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.5.0...v0.5.1) (2026-08-05)


### Bug Fixes

* refuse Playwright at primary checkouts ([30ce7dc](https://github.com/thewoolleyman/livespec-driver-claude/commit/30ce7dcb8aa8ce155cf66f6cea29bbe9c362e830))

## [0.5.0](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.4.9...v0.5.0) (2026-08-05)


### Features

* guard repeated github api calls ([776827d](https://github.com/thewoolleyman/livespec-driver-claude/commit/776827d6da5ce646cc814c51f1c6dacfb79e571b))

## [0.4.9](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.4.8...v0.4.9) (2026-08-01)


### Bug Fixes

* **skills:** resolve core by projectPath, not by position in the registry ([99bfac0](https://github.com/thewoolleyman/livespec-driver-claude/commit/99bfac0beb82832472e29a7e8a89f6dd3a2cde72))

## [0.4.8](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.4.7...v0.4.8) (2026-07-26)


### Refactoring

* **tests:** stop hand-copying the closed BLE001 marker set ([5626956](https://github.com/thewoolleyman/livespec-driver-claude/commit/56269561c6b317aa21cea875e7dd070187b73e21))

## [0.4.7](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.4.6...v0.4.7) (2026-07-26)


### Bug Fixes

* **config:** describe the current role-key regime, not the retired fallback ([0d0576b](https://github.com/thewoolleyman/livespec-driver-claude/commit/0d0576b55c0fd64a82425d8c1c1230415d6b9455))

## [0.4.6](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.4.5...v0.4.6) (2026-07-24)


### Bug Fixes

* route growing jq inputs to stdin in the CI telemetry export ([ea88d98](https://github.com/thewoolleyman/livespec-driver-claude/commit/ea88d984fdb02c1597a80e7d01700137dda35a03))

## [0.4.5](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.4.4...v0.4.5) (2026-07-23)


### Bug Fixes

* pin no-shadow-ledger body byte-identity to the packaged canonical ([f35425c](https://github.com/thewoolleyman/livespec-driver-claude/commit/f35425ca7b83b407699eec5054acadb916be0b8d))

## [0.4.4](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.4.3...v0.4.4) (2026-07-19)


### Bug Fixes

* **hooks:** scan every token position for a tmux command head ([d9ec17b](https://github.com/thewoolleyman/livespec-driver-claude/commit/d9ec17b1b71dd75bda1683795fa05441e941d53c))

## [0.4.3](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.4.2...v0.4.3) (2026-07-19)


### Bug Fixes

* **hooks:** close demonstrated tmux fleet-kill guard bypasses ([27e4131](https://github.com/thewoolleyman/livespec-driver-claude/commit/27e413173adee93051db489d32dcd3c1cb2cae51))

## [0.4.2](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.4.1...v0.4.2) (2026-07-19)


### Bug Fixes

* harden hook broad-except boundaries ([4b496e1](https://github.com/thewoolleyman/livespec-driver-claude/commit/4b496e1d79d1cedf31211d9c084b5dc397391bfd))

## [0.4.1](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.4.0...v0.4.1) (2026-07-19)


### Bug Fixes

* **hooks:** make plugin-shipped hooks self-contained under bare python3 ([fced250](https://github.com/thewoolleyman/livespec-driver-claude/commit/fced2508025a6c37cc7a5eca5f1aeb8235e9efb2))


### Refactoring

* **hooks:** swap the shipped railway to the self-contained _result shim ([b1b339d](https://github.com/thewoolleyman/livespec-driver-claude/commit/b1b339d00b374c2435d8d764c1319c74e8e5169c))

## [0.4.0](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.3.0...v0.4.0) (2026-07-19)


### Features

* adopt hook ROP policy ([b73260e](https://github.com/thewoolleyman/livespec-driver-claude/commit/b73260ee22a60787884b9afda5f1e4249166eb72))

## [0.3.0](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.2.3...v0.3.0) (2026-07-19)


### Features

* bundle tmux fleet guard hook ([340dff8](https://github.com/thewoolleyman/livespec-driver-claude/commit/340dff81dfbbbd54c8436b3c30e009136b8a8f66))

## [0.2.3](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.2.2...v0.2.3) (2026-07-13)


### Refactoring

* make plugin-shipped Claude hooks importable + full CI parity (S3+S5) ([1722a60](https://github.com/thewoolleyman/livespec-driver-claude/commit/1722a60ac7818d254be52e7af6932e240c18bdfa))

## [0.2.2](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.2.1...v0.2.2) (2026-07-12)


### Refactoring

* **hooks:** make footgun guard structurally coverage-clean ([4489fca](https://github.com/thewoolleyman/livespec-driver-claude/commit/4489fcafde36e3edaf449c2922279bd18f23fdea))

## [0.2.1](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.2.0...v0.2.1) (2026-07-01)


### Bug Fixes

* point plugin-structure recipe at driver_checks + bump dt pin to v0.25.1 (livespec-2exa) ([6e168b2](https://github.com/thewoolleyman/livespec-driver-claude/commit/6e168b249c03f9c382ad0a25be319004447118f5))


### Refactoring

* consume check_plugin_structure from the livespec-dev-tooling package; drop vendored copy (zs22.7.9.2) ([08f0e9c](https://github.com/thewoolleyman/livespec-driver-claude/commit/08f0e9c3c512e2924854e966bc8dd33a9f14a635))

## [0.2.0](https://github.com/thewoolleyman/livespec-driver-claude/compare/v0.1.0...v0.2.0) (2026-06-24)


### Features

* bootstrap the livespec-driver-claude Driver plugin ([ca90310](https://github.com/thewoolleyman/livespec-driver-claude/commit/ca90310a9f2ec99606126c5a88cc090975c9e43b))
* **hooks:** ship PreToolUse hook redirecting auto-memory writes to capture-memo ([dcfde10](https://github.com/thewoolleyman/livespec-driver-claude/commit/dcfde10a475c1b078718dd7b3b34f999c857131a))
* **hooks:** ship Stop hook warning on unpersisted plan artifacts ([75603ce](https://github.com/thewoolleyman/livespec-driver-claude/commit/75603ce64a23fcc864e60f10d72c35e89d42c036))
* relocate the CLI e2e harness consumer from livespec core ([21feed0](https://github.com/thewoolleyman/livespec-driver-claude/commit/21feed0dc083d1c0eedc0d095d31885e5cfc4b5e))


### Bug Fixes

* **next:** drop the retired loop-driver nudge from the runtime-binding table ([f602235](https://github.com/thewoolleyman/livespec-driver-claude/commit/f6022352ee3578b95e13038c3766e590af21b519))


### Refactoring

* flip stray livespec-impl-beads plugin/namespace refs to livespec-orchestrator-beads-fabro (S11) ([587f28e](https://github.com/thewoolleyman/livespec-driver-claude/commit/587f28e3b80608a56b334d1cafc9f0a857bfff3c))

## Changelog

All notable changes to this plugin are recorded here. This file is
auto-maintained by release-please; do not edit it by hand.
