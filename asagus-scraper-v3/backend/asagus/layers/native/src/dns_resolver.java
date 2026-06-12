/**
 * ASAGUS DNS Resolver — Custom DNS-over-HTTPS
 * =============================================
 * Resolves domain names via DNS-over-HTTPS (DoH) to prevent DNS leaks
 * that could reveal scraper identity to ISPs and detection systems.
 *
 * Supports:
 * - Cloudflare DoH (1.1.1.1)
 * - Google DoH (8.8.8.8)
 * - Quad9 DoH (9.9.9.9)
 *
 * Usage:
 *   java dns_resolver <domain> [--provider cloudflare|google|quad9] [--type A|AAAA]
 *
 * Output: JSON with resolved addresses
 *
 * FOR EDUCATION AND RESEARCH PURPOSES ONLY
 */

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import javax.net.ssl.*;

public class dns_resolver {

    private static final Map<String, String> DOH_PROVIDERS = new LinkedHashMap<>();
    static {
        DOH_PROVIDERS.put("cloudflare", "https://cloudflare-dns.com/dns-query");
        DOH_PROVIDERS.put("google", "https://dns.google/resolve");
        DOH_PROVIDERS.put("quad9", "https://dns.quad9.net/dns-query");
    }

    public static void main(String[] args) {
        if (args.length < 1) {
            printUsage(System.err);
            System.exit(1);
        }

        String domain = args[0];

        if ("--help".equals(domain)) {
            printUsage(System.out);
            System.exit(0);
        }

        String provider = "cloudflare";
        String recordType = "A";
        int timeoutMs = 10000;

        for (int i = 1; i < args.length; i++) {
            switch (args[i]) {
                case "--provider":
                    if (i + 1 < args.length) provider = args[++i].toLowerCase();
                    break;
                case "--type":
                    if (i + 1 < args.length) recordType = args[++i].toUpperCase();
                    break;
                case "--timeout":
                    if (i + 1 < args.length) timeoutMs = Integer.parseInt(args[++i]);
                    break;
            }
        }

        try {
            String result = resolveDoH(domain, provider, recordType, timeoutMs);
            System.out.println(result);
        } catch (Exception e) {
            System.out.println(errorJson(domain, e.getMessage()));
            System.exit(1);
        }
    }

    private static String resolveDoH(String domain, String provider, String recordType, int timeoutMs) throws Exception {
        String dohUrl = DOH_PROVIDERS.getOrDefault(provider, DOH_PROVIDERS.get("cloudflare"));

        // Build DoH JSON API request
        String separator = dohUrl.contains("?") ? "&" : "?";
        String requestUrl = dohUrl + separator + "name=" + URLEncoder.encode(domain, "UTF-8")
            + "&type=" + URLEncoder.encode(recordType, "UTF-8");

        URL url = new URL(requestUrl);
        HttpURLConnection conn;

        if (requestUrl.startsWith("https://")) {
            HttpsURLConnection httpsConn = (HttpsURLConnection) url.openConnection();
            httpsConn.setSSLSocketFactory(createTrustingSSLContext().getSocketFactory());
            conn = httpsConn;
        } else {
            conn = (HttpURLConnection) url.openConnection();
        }

        conn.setRequestMethod("GET");
        conn.setConnectTimeout(timeoutMs);
        conn.setReadTimeout(timeoutMs);
        conn.setRequestProperty("Accept", "application/dns-json");
        conn.setRequestProperty("User-Agent", "ASAGUS-DNS-Resolver/1.0");

        long startTime = System.currentTimeMillis();
        int statusCode = conn.getResponseCode();
        long elapsed = System.currentTimeMillis() - startTime;

        String responseBody;
        try (InputStream is = (statusCode >= 400) ? conn.getErrorStream() : conn.getInputStream()) {
            responseBody = readStream(is);
        }
        conn.disconnect();

        // Parse DoH JSON response to extract Answer records
        List<String> addresses = new ArrayList<>();
        List<String> cnames = new ArrayList<>();
        int ttl = 0;

        // Simple JSON parsing (no external library dependency)
        String[] answerParts = responseBody.split("\"Answer\"");
        if (answerParts.length > 1) {
            String answerSection = answerParts[1];
            // Extract "data" fields
            String[] dataParts = answerSection.split("\"data\"\\s*:\\s*\"");
            for (int i = 1; i < dataParts.length; i++) {
                String data = dataParts[i].split("\"")[0].trim();
                if (data.matches("\\d+\\.\\d+\\.\\d+\\.\\d+")) {
                    addresses.add(data);
                } else if (data.contains(":")) {
                    addresses.add(data); // IPv6
                } else if (data.contains(".")) {
                    cnames.add(data); // CNAME
                }
            }
            // Extract TTL
            String[] ttlParts = answerSection.split("\"TTL\"\\s*:\\s*");
            if (ttlParts.length > 1) {
                try {
                    ttl = Integer.parseInt(ttlParts[1].split("[,}\\]]")[0].trim());
                } catch (NumberFormatException e) {
                    ttl = 0;
                }
            }
        }

        // Build JSON response
        StringBuilder json = new StringBuilder();
        json.append("{");
        json.append("\"domain\":\"").append(escapeJson(domain)).append("\",");
        json.append("\"provider\":\"").append(escapeJson(provider)).append("\",");
        json.append("\"record_type\":\"").append(escapeJson(recordType)).append("\",");
        json.append("\"status\":").append(statusCode).append(",");
        json.append("\"elapsed_ms\":").append(elapsed).append(",");
        json.append("\"ttl\":").append(ttl).append(",");
        json.append("\"addresses\":[");
        for (int i = 0; i < addresses.size(); i++) {
            if (i > 0) json.append(",");
            json.append("\"").append(escapeJson(addresses.get(i))).append("\"");
        }
        json.append("],");
        json.append("\"cnames\":[");
        for (int i = 0; i < cnames.size(); i++) {
            if (i > 0) json.append(",");
            json.append("\"").append(escapeJson(cnames.get(i))).append("\"");
        }
        json.append("],");
        json.append("\"resolved\":").append(!addresses.isEmpty());
        json.append("}");

        return json.toString();
    }

    private static SSLContext createTrustingSSLContext() throws Exception {
        SSLContext ctx = SSLContext.getInstance("TLS");
        ctx.init(null, new TrustManager[]{
            new X509TrustManager() {
                public java.security.cert.X509Certificate[] getAcceptedIssuers() { return null; }
                public void checkClientTrusted(java.security.cert.X509Certificate[] certs, String authType) {}
                public void checkServerTrusted(java.security.cert.X509Certificate[] certs, String authType) {}
            }
        }, new java.security.SecureRandom());
        return ctx;
    }

    private static String readStream(InputStream stream) throws IOException {
        if (stream == null) return "";
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            char[] buffer = new char[4096];
            int read;
            while ((read = reader.read(buffer)) != -1) {
                sb.append(buffer, 0, read);
            }
        }
        return sb.toString();
    }

    private static String escapeJson(String value) {
        if (value == null) return "";
        return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r");
    }

    private static String errorJson(String domain, String message) {
        return "{\"domain\":\"" + escapeJson(domain) + "\",\"error\":\"" + escapeJson(message) + "\",\"resolved\":false}";
    }

    private static void printUsage(PrintStream out) {
        out.println("ASAGUS DNS Resolver — DNS-over-HTTPS");
        out.println("Usage: java dns_resolver <domain> [options]");
        out.println("Options:");
        out.println("  --provider <name>  DoH provider: cloudflare, google, quad9 (default: cloudflare)");
        out.println("  --type <type>      DNS record type: A, AAAA (default: A)");
        out.println("  --timeout <ms>     Request timeout in milliseconds (default: 10000)");
        out.println("  --help             Show this help");
    }
}
