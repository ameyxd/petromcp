# Supported formats

| Format | Status   | Library | Notes                                   |
|--------|----------|---------|-----------------------------------------|
| LAS    | Shipping | lasio   | Header + per-curve summary + curve read |
| DLIS   | Planned  | dlisio  | Next slice                              |
| SEG-Y  | Planned  | segyio  | Headers only; trace data is out of scope|
| Pump   | Planned  | csv     | After SEG-Y                             |
| WITSML | v2       | -       | Real-time streaming, deferred           |

LAS files compliant with versions 1.2, 2.0, and 3.0 (insofar as `lasio`
supports them) work. Malformed headers fall through to a structured error
rather than crashing the server.
