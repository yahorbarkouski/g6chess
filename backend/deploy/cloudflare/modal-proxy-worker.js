export default {
  async fetch(request, env) {
    const originHost = env.MODAL_ORIGIN_HOST;
    if (!originHost) {
      return new Response("MODAL_ORIGIN_HOST is not configured.", { status: 500 });
    }
    if (!env.MODAL_KEY || !env.MODAL_SECRET) {
      return new Response("Modal proxy credentials are not configured.", { status: 500 });
    }

    const originUrl = new URL(request.url);
    originUrl.protocol = "https:";
    originUrl.hostname = originHost;

    const headers = new Headers(request.headers);
    headers.delete("Modal-Key");
    headers.delete("Modal-Secret");
    headers.set("Modal-Key", env.MODAL_KEY);
    headers.set("Modal-Secret", env.MODAL_SECRET);

    const init = {
      method: request.method,
      headers,
      redirect: "manual",
    };
    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = request.body;
    }

    return fetch(originUrl, init);
  },
};
