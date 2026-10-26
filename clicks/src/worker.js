// digest 私有站的点击记录后台：页面用 sendBeacon 发 POST，这里只管写进 D1。
// 故意不提供读接口：数据用 `wrangler d1 execute digest-clicks --remote` 读，
// 这样后台对外只有"写"这一个口子，不用为读另配密钥。
//
// 私有站没有访问控制，这个地址谁都能看到。Origin 检查挡不住有心人(curl 可以随便伪造)，
// 只是让别的网站没法顺手往这里写。数据只用于分析自己的阅读习惯，被灌几条假数据代价很小。

const SITE_ORIGIN = 'https://yyeees.github.io';
const LOCAL_ORIGIN = /^http:\/\/(localhost|127\.0\.0\.1):\d+$/;   // 本地 http.server 预览，端口不固定
const allowed = o => o === SITE_ORIGIN || LOCAL_ORIGIN.test(o || '');
const TYPES = new Set(['view', 'click', 'expand']);
const MAX_BODY = 32 * 1024;   // view 事件带着整页的链接列表，七天一百来条，远小于这个数

export default {
  async fetch(request, env) {
    if (request.method !== 'POST') return new Response('only POST', { status: 405 });
    if (!allowed(request.headers.get('Origin'))) return new Response('bad origin', { status: 403 });

    // sendBeacon 发的是 text/plain，不触发 CORS 预检，所以这里不解析 Content-Type，直接按 JSON 读
    const text = await request.text();
    if (text.length > MAX_BODY) return new Response('too large', { status: 413 });
    let ev;
    try { ev = JSON.parse(text); } catch (e) { return new Response('bad json', { status: 400 }); }
    if (!ev || !TYPES.has(ev.type)) return new Response('bad type', { status: 400 });

    const { type, link = null, ...data } = ev;
    await env.DB.prepare('INSERT INTO events (ts, type, link, data) VALUES (?, ?, ?, ?)')
      .bind(new Date().toISOString(), type, link, JSON.stringify(data))
      .run();
    return new Response(null, { status: 204 });
  },
};
