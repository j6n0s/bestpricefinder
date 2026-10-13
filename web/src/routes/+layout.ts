// Single-page app: nothing is rendered on a server or prerendered. adapter-static writes build/index.html as
// the fallback page that the server returns for every non-/api path.
export const ssr = false;
export const prerender = false;
