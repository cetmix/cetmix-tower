## 18.0.2.1.2 (2026-09-17)

- Bugfixes: A ``file_using_template`` command no longer enqueues a second file
  upload or download job. The transfer runs inside the command job, so
  the command log finishes only after the file is on the host and a
  failed transfer fails the plan line. (5625)


## 18.0.2.1.0 (2026-09-14)

- Features: Register as sequence-50 deferral backend and queue nested-plan SSH instead of forcing it to run in-process. (5596)


## 18.0.2.0.0 (2026-04-07)

- Features: Jets! (4700)
