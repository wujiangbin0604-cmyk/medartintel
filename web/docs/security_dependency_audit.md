# npm 依赖安全审计

执行日期：2026-11-03。原始 JSON、锁文件前快照与安装日志在本目录保留。未执行 `npm audit fix --force`。

| 阶段 | low | moderate | high | critical | total |
| --- | ---: | ---: | ---: | ---: | ---: |
| 修复前 | 10 | 46 | 17 | 1 | 74 |
| 修复后 | 10 | 44 | 16 | 1 | 71 |
| 修复后 --omit=dev | 10 | 44 | 16 | 1 | 71 |

## 已实施的最小更新

- `@babel/runtime` 7.23.6 → 7.29.10，同属 major 7；覆盖 Umi 旧的精确传递依赖。
- `postcss` 8.4.31 → 8.5.32，同属 major 8；更新匹配 `^8.4.21` 的传递依赖。
- 实际锁文件版本变化仅这两个包。npm 同时移除 17 个被合并的重复包，详见 `phase3_dependency_install.log` 与 `phase3_package_lock_before.json`。
- 消失的审计条目：`@babel/runtime`、其影响的 `@umijs/babel-preset-umi` 和 `postcss`。直接 React / Ant Design / ECharts / Umi 版本未强行迁移。
- 候选版本查询发现 immer 8.x 无可用安全补丁、decode-uri-component 0.2.x 没有新补丁；未安装不存在的候选版本。最终 package.json 仅保留已实际安装的两个 overrides。

## 依赖性质与实际暴露

`@umijs/max` 在原 package.json 被列为 dependencies，因此 npm --omit=dev 仍会包含构建器、开发服务器、lint 和插件链。不能把该结果解释为“生产静态页面包含全部告警代码”，也不能因此把这些包认定为无风险。测试工具本身为 devDependencies；本轮 71 项告警均通过 Umi 的 dependencies 树保留。

- 浏览器可达链需关注 react-router / react-router-dom、query-string / decode-uri-component。当前导航为固定本地路由，未接收任意外部跳转地址。
- `axios` 0.27.2 由 @umijs/plugins 精确引入；项目接口使用原生 fetch。
- critical 为 `immer` 8.0.4 的旧原型污染问题，经 dva-immer 插件引入；本项目未启用 dva/store 插件。仍保留告警，不声称安全。
- node-fetch 1.x、esbuild、glob、minimatch、Vite、path-to-regexp 等分属旧插件/开发/构建链；本地演示不公开开发服务。
- npm 提供的部分自动“修复”是把 @umijs/max 改为 4.0.7，属于不合适的跨依赖树变更。本轮未执行。

## 未修复告警清单

| 包 | 严重度 | 直接依赖 | 受影响范围 | 原始公告 / 影响链 |
| --- | --- | --- | --- | --- |
| @ant-design/pro-components | high | 传递 | 2.7.18 - 2.8.10 | @ant-design/pro-layout |
| @ant-design/pro-layout | high | 传递 | >=7.20.1 | path-to-regexp |
| @babel/core | low | 传递 | <=7.29.0 | [@babel/core: Arbitrary File Read via sourceMappingURL Comment](https://github.com/advisories/GHSA-4x5r-pxfx-6jf8) |
| @babel/eslint-parser | moderate | 传递 | * | eslint |
| @esbuild-kit/cjs-loader | moderate | 传递 | * | @esbuild-kit/core-utils |
| @esbuild-kit/core-utils | moderate | 传递 | * | esbuild |
| @esbuild-kit/esm-loader | moderate | 传递 | * | @esbuild-kit/core-utils |
| @eslint-community/eslint-utils | moderate | 传递 | * | eslint |
| @eslint/eslintrc | moderate | 传递 | 0.0.1 || >=0.1.1 | minimatch |
| @hono/node-server | moderate | 传递 | 1.19.10 - 2.1.2 | [@hono/node-server: `serveStatic` decodes the request path a second time, leading to bypass of middleware on static paths](https://github.com/advisories/GHSA-rmxm-3fg6-px4f) |
| @hono/node-ws | moderate | 传递 | >=1.3.1 | @hono/node-server |
| @humanwhocodes/config-array | moderate | 传递 | * | minimatch |
| @jest/transform | moderate | 传递 | * | babel-plugin-istanbul |
| @svgr/plugin-svgo | low | 传递 | >=5.5.0 | deepmerge |
| @typescript-eslint/eslint-plugin | moderate | 传递 | * | @typescript-eslint/parser；@typescript-eslint/type-utils；@typescript-eslint/utils；eslint |
| @typescript-eslint/parser | moderate | 传递 | * | eslint |
| @typescript-eslint/type-utils | moderate | 传递 | >=5.9.2-alpha.0 | @typescript-eslint/utils |
| @typescript-eslint/utils | moderate | 传递 | * | @eslint-community/eslint-utils；eslint |
| @umijs/bundler-mako | moderate | 传递 | * | @umijs/mako；rimraf |
| @umijs/bundler-utoopack | moderate | 传递 | * | @umijs/bundler-webpack；@utoo/pack |
| @umijs/bundler-vite | moderate | 传递 | >=4.6.68 | @umijs/bundler-webpack；vite |
| @umijs/bundler-webpack | moderate | 传递 | >=3.4.0-beta.1 | @svgr/plugin-svgo；fork-ts-checker-webpack-plugin；node-libs-browser |
| @umijs/history | high | 传递 | * | query-string |
| @umijs/lint | moderate | 传递 | * | @babel/core；@babel/eslint-parser；@typescript-eslint/eslint-plugin；@typescript-eslint/parser；eslint-plugin-jest；eslint-plugin-react；stylelint-config-standard |
| @umijs/mako | low | 传递 | * | node-libs-browser-okam |
| @umijs/max | high | 是 | * | @umijs/lint；@umijs/plugins；eslint；stylelint；umi |
| @umijs/plugin-run | moderate | 传递 | <=4.0.0-canary-20240513.3 || >=4.1.2 | tsx |
| @umijs/plugins | high | 传递 | * | axios；dva-immer |
| @umijs/preset-umi | high | 传递 | * | @umijs/bundler-mako；@umijs/bundler-utoopack；@umijs/bundler-vite；@umijs/bundler-webpack；@umijs/history；@umijs/plugin-run；@umijs/renderer-react；@umijs/server；path-to-regexp；react-router；react-router-dom |
| @umijs/renderer-react | moderate | 传递 | >=4.0.0-beta.1 | @umijs/server；react-router-dom |
| @umijs/server | moderate | 传递 | >=4.0.0-beta.1 | react-router-dom |
| @umijs/test | moderate | 传递 | <=4.0.0-rc.24 || >=4.0.13 | babel-jest |
| @utoo/pack | moderate | 传递 | >=1.3.0-alpha.0 | @hono/node-server |
| axios | high | 传递 | <=0.33.0 | [Axios Cross-Site Request Forgery Vulnerability](https://github.com/advisories/GHSA-wf5p-g6vw-rhxx)；[axios Requests Vulnerable To Possible SSRF and Credential Leakage via Absolute URL](https://github.com/advisories/GHSA-jr5f-v2jv-69x6)；[Axios has a NO_PROXY Hostname Normalization Bypass that Leads to SSRF](https://github.com/advisories/GHSA-3p68-rc4w-qgx5)；[Axios: Authentication Bypass via Prototype Pollution Gadget in `validateStatus` Merge Strategy](https://github.com/advisories/GHSA-w9j2-pvgh-6h63)；[Axios: Incomplete Fix for CVE-2025-62718 — NO_PROXY Protection Bypassed via RFC 1122 Loopback Subnet (127.0.0.0/8) in Axios 1.15.0](https://github.com/advisories/GHSA-pmwg-cvhr-8vh7)；[Axios: Null Byte Injection via Reverse-Encoding in AxiosURLSearchParams](https://github.com/advisories/GHSA-xhjh-pmcv-23jw)；[Axios: no_proxy bypass via IP alias allows SSRF](https://github.com/advisories/GHSA-m7pr-hjqh-92cm)；[Axios' HTTP adapter-streamed uploads bypass maxBodyLength when maxRedirects: 0](https://github.com/advisories/GHSA-5c9x-8gcm-mpgx)；[Axios: HTTP adapter streamed responses bypass maxContentLength](https://github.com/advisories/GHSA-vf2m-468p-8v99)；[Axios: Prototype Pollution Gadgets - Response Tampering, Data Exfiltration, and Request Hijacking](https://github.com/advisories/GHSA-pf86-5x62-jrwf)；[Axios: Header Injection via Prototype Pollution](https://github.com/advisories/GHSA-6chq-wfr3-2hj9)；[Axios: XSRF Token Cross-Origin Leakage via Prototype Pollution Gadget in `withXSRFToken` Boolean Coercion](https://github.com/advisories/GHSA-xx6v-rp6x-q39c)；[Axios is Vulnerable to Denial of Service via __proto__ Key in mergeConfig](https://github.com/advisories/GHSA-43fc-jf86-j433)；[Axios has Unrestricted Cloud Metadata Exfiltration via Header Injection Chain](https://github.com/advisories/GHSA-fvcv-3m26-pcqx)；[Axios: unbounded recursion in toFormData causes DoS via deeply nested request data](https://github.com/advisories/GHSA-62hf-57xw-28j9)；[Axios: Regular Expression Denial of Service (ReDoS) via Cookie Name Injection](https://github.com/advisories/GHSA-hfxv-24rg-xrqf)；[Axios: Proxy-Authorization Credential Leak to Origin Server Across HTTP-to-HTTPS Redirect in Axios Node.js HTTP Adapter](https://github.com/advisories/GHSA-p92q-9vqr-4j8v)；[Axios: Proxy-Authorization header leaks to redirect target when proxy is re-evaluated to direct connection](https://github.com/advisories/GHSA-j5f8-grm9-p9fc)；[axios Vulnerable to Credential Theft and Response Hijacking via Prototype Pollution Gadget in Config Merge](https://github.com/advisories/GHSA-3g43-6gmg-66jw)；[axios has DoS & Header Injection via Prototype Pollution Read-Side Gadgets in axios merge functions](https://github.com/advisories/GHSA-898c-q2cr-xwhg)；[axios's shouldBypassProxy does not recognize IPv4-mapped IPv6 addresses, allowing NO_PROXY bypass (incomplete fix for CVE-2025-62718)](https://github.com/advisories/GHSA-pjwm-pj3p-43mv)；[Axios: Prototype pollution gadgets can alter axios request construction](https://github.com/advisories/GHSA-mmx7-hfxf-jppx)；[Axios: Nested axios option objects can consume polluted prototype values](https://github.com/advisories/GHSA-7q8q-rj6j-mhjq)；[Axios: Prototype-Pollution Gadget in the Default Instance Allows Inherited Object.prototype.method to Override HTTP Method](https://github.com/advisories/GHSA-9fr6-4gfg-395g) |
| babel-jest | moderate | 传递 | >=24.0.0-alpha.0 | @jest/transform；babel-plugin-istanbul |
| babel-plugin-istanbul | moderate | 传递 | >=5.0.1 | test-exclude |
| browserify-sign | low | 传递 | >=2.4.0 | elliptic |
| create-ecdh | low | 传递 | * | elliptic |
| crypto-browserify | low | 传递 | >=3.4.0 | browserify-sign；create-ecdh |
| decode-uri-component | high | 传递 | <=0.5.0 | [decode-uri-component: Denial of service via exponential decoding of malformed percent-encoded input](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr)；[decode-uri-component vulnerable to denial of service via quadratic replacement of percent-encoded runs](https://github.com/advisories/GHSA-qr28-fpjm-wq7f) |
| deepmerge | low | 传递 | >=4.2.0 | [deepmerge mergeObject() allows prototype poisoning of returned objects](https://github.com/advisories/GHSA-gcqx-w48m-w2h4) |
| dva | high | 传递 | 0.0.2 - 0.0.9 || >=1.2.0-beta1 | isomorphic-fetch |
| dva-immer | high | 传递 | * | dva；immer |
| elliptic | low | 传递 | * | [Elliptic Uses a Cryptographic Primitive with a Risky Implementation](https://github.com/advisories/GHSA-848j-6mx2-7j84) |
| esbuild | moderate | 传递 | <=0.24.2 | [esbuild enables any website to send any requests to the development server and read the response](https://github.com/advisories/GHSA-67mh-4wv8-2f99) |
| eslint | moderate | 传递 | 0.7.1 - 2.0.0-rc.1 || >=4.1.0 | @eslint/eslintrc；@humanwhocodes/config-array；eslint-utils；file-entry-cache；minimatch |
| eslint-plugin-jest | moderate | 传递 | >=22.0.0 | @typescript-eslint/eslint-plugin；@typescript-eslint/utils；eslint |
| eslint-plugin-react | moderate | 传递 | >=7.23.0 | minimatch |
| eslint-utils | moderate | 传递 | >=3.0.0 | eslint |
| file-entry-cache | moderate | 传递 | 4.0.0 - 7.0.2 | flat-cache |
| flat-cache | moderate | 传递 | 1.3.4 - 4.0.0 | rimraf |
| fork-ts-checker-webpack-plugin | moderate | 传递 | >=0.2.9 | deepmerge；minimatch |
| glob | moderate | 传递 | 3.0.0 - 14.0.1 | [Glob: AbortSignal cancellation bypass allows post-timeout filesystem traversal](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4)；minimatch |
| immer | critical | 传递 | 7.0.0 - 9.0.5 | [Prototype Pollution in immer](https://github.com/advisories/GHSA-c36v-fmgq-m8hx)；[Prototype Pollution in immer](https://github.com/advisories/GHSA-33f9-j839-rf8h) |
| isomorphic-fetch | high | 传递 | 2.0.0 - 2.2.1 | node-fetch |
| minimatch | moderate | 传递 | <11.0.1 | [minimatch has potential denial of service via globparts amplification](https://github.com/advisories/GHSA-g3hv-75wg-m249) |
| node-fetch | high | 传递 | <2.6.7 | [node-fetch forwards secure headers to untrusted sites](https://github.com/advisories/GHSA-r683-j2x4-v87g) |
| node-libs-browser | low | 传递 | 0.4.2 || >=1.0.0 | crypto-browserify |
| node-libs-browser-okam | low | 传递 | * | crypto-browserify |
| path-to-regexp | high | 传递 | 0.2.0 - 1.8.0 || 8.0.0 - 8.3.0 | [path-to-regexp outputs backtracking regular expressions](https://github.com/advisories/GHSA-9wv6-86v2-598j)；[path-to-regexp vulnerable to Denial of Service via sequential optional groups](https://github.com/advisories/GHSA-j3q9-mxjg-w52f)；[path-to-regexp vulnerable to Regular Expression Denial of Service via multiple wildcards](https://github.com/advisories/GHSA-27v5-c462-wpq7) |
| query-string | high | 传递 | 5.0.0 - 9.4.1 | decode-uri-component |
| react-router | moderate | 传递 | 6.0.0 - 7.17.0 | [React Router has unexpected external redirect via untrusted paths](https://github.com/advisories/GHSA-9jcx-v3wj-wh4m)；[React Router: Open redirect via backslash in <Link> and useNavigate (CVE-2025-68470 bypass)](https://github.com/advisories/GHSA-wrjc-x8rr-h8h6) |
| react-router-dom | moderate | 传递 | 6.0.0-alpha.0 - 6.30.2-pre-v6.0 | react-router |
| rimraf | moderate | 传递 | 2.3.0 - 3.0.2 || >=4.2.0 | glob；glob |
| stylelint | moderate | 传递 | 9.10.1 - 16.0.2 | file-entry-cache |
| stylelint-config-recommended | moderate | 传递 | 4.0.0 - 13.0.0 | stylelint |
| stylelint-config-standard | moderate | 传递 | 21.0.0 - 34.0.0 | stylelint；stylelint-config-recommended |
| test-exclude | moderate | 传递 | 4.2.2 || >=5.0.0 | glob；minimatch |
| tsx | moderate | 传递 | 2.0.0 - 3.12.10 | @esbuild-kit/cjs-loader；@esbuild-kit/core-utils；@esbuild-kit/esm-loader |
| umi | high | 传递 | >=4.0.0-beta.1 | @umijs/bundler-webpack；@umijs/preset-umi；@umijs/renderer-react；@umijs/server；@umijs/test |
| vite | high | 传递 | 7.0.0 - 7.3.6 | [launch-editor: escapeCmdArgs() omits % escaping on Windows](https://github.com/advisories/GHSA-698v-4r3x-3vcv)；[launch-editor: Editor CLI flag misinterpretation causing arbitrary command execution for some editors](https://github.com/advisories/GHSA-r825-w8mm-5pxw)；[launch-editor: `fs.existsSync()` existence check can be bypassed on Windows](https://github.com/advisories/GHSA-587h-7wmj-h5pm)；[Vite: Cross origin script execution through Vite custom middleware](https://github.com/advisories/GHSA-9jrq-w75r-8gcw)；[Vite: Files outside `server.fs.allow` could be served when project paths match system paths on non-Windows machine](https://github.com/advisories/GHSA-rq7h-c2jc-7f22) |

## 验证与后续

命令：`npm audit --json`、`npm audit --omit=dev --json`、`npm view immer@8 version --json`、`npm view decode-uri-component@0.2 version --json`、`npm install --ignore-scripts --no-fund`。首次沙箱 DNS 请求失败后，以授权网络访问取得真实审计；失败结果没有当作零告警。

最终类型检查、构建与浏览器回归日志见 `phase3_typecheck.log`、`phase3_build.log`、`phase3_e2e_final.log`、`phase3_production_e2e.log`。

独立后续任务：升级 Umi / 插件生态，评估移除未启用的 dva/旧 fetch 链，验证路由安全修复所需的大版本兼容性。当前版本仅用于 loopback 课程演示；公开部署前需另行处理残余高危依赖与访问控制。
