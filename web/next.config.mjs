/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Compile to plain HTML/CSS/JS so Django can serve the site and the API from
  // one origin. Every page is a client component, so nothing here needs a Node
  // server at runtime.
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
