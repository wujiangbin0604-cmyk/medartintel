// Umi reads PORT from the environment; --port is not its listen-port setting.
process.env.PORT = process.env.PORT || '8001';
require('@umijs/max/bin/max.js');
