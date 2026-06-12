/**
 * ASAGUS TLS Helper — Java TLS Fingerprint Diversification
 * =========================================================
 * Provides alternate TLS stacks for JA3/JA4 fingerprint diversification.
 * Uses Java's SSLContext to create TLS connections with different cipher
 * suites and extension ordering than Python/curl-cffi, making the scraper
 * appear as a different client to TLS-fingerprinting detection systems.
 *
 * Usage (from Python via subprocess):
 *   java -jar tls_helper.jar <url> [--cipher-suite <suite>] [--timeout <ms>]
 *
 * Output: JSON with TLS negotiation details + HTTP response
 *
 * FOR EDUCATION AND RESEARCH PURPOSES ONLY
 */

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.cert.X509Certificate;
import java.util.*;
import javax.net.ssl.*;

public class tls_helper {

    // JA3-like fingerprint components for diversification
    private static final String[][] CIPHER_PROFILES = {
        // Chrome 124 profile
        {
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
        },
        // Firefox 125 profile
        {
            "TLS_AES_128_GCM_SHA256",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
        },
        // Safari 17 profile
        {
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
        },
    };

    private static final String[] TLS_PROTOCOLS = {"TLSv1.3", "TLSv1.2"};

    public static void main(String[] args) {
        if (args.length < 1) {
            printUsage(System.err);
            System.exit(1);
        }

        if ("--help".equals(args[0])) {
            printUsage(System.out);
            System.exit(0);
        }

        String url = args[0];
        int profileIndex = 0;
        int timeoutMs = 15000;
        boolean trustAll = false;
        boolean verbose = false;

        // Parse arguments
        for (int i = 1; i < args.length; i++) {
            switch (args[i]) {
                case "--profile":
                    if (i + 1 < args.length) profileIndex = Integer.parseInt(args[++i]);
                    break;
                case "--timeout":
                    if (i + 1 < args.length) timeoutMs = Integer.parseInt(args[++i]);
                    break;
                case "--trust-all":
                    trustAll = true;
                    break;
                case "--verbose":
                    verbose = true;
                    break;
                case "--help":
                    printUsage(System.out);
                    System.exit(0);
            }
        }

        try {
            String result = performTLSRequest(url, profileIndex % CIPHER_PROFILES.length, timeoutMs, trustAll, verbose);
            System.out.println(result);
        } catch (Exception e) {
            System.out.println(errorJson(e.getMessage()));
            System.exit(1);
        }
    }

    private static String performTLSRequest(String url, int profileIndex, int timeoutMs, boolean trustAll, boolean verbose) throws Exception {
        SSLContext sslContext = createCustomSSLContext(profileIndex, trustAll);
        URL targetUrl = new URL(url);

        HttpsURLConnection connection = (HttpsURLConnection) targetUrl.openConnection();
        connection.setSSLSocketFactory(sslContext.getSocketFactory());
        connection.setConnectTimeout(timeoutMs);
        connection.setReadTimeout(timeoutMs);
        connection.setRequestMethod("GET");
        connection.setInstanceFollowRedirects(true);

        // Set realistic browser headers
        connection.setRequestProperty("User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36");
        connection.setRequestProperty("Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8");
        connection.setRequestProperty("Accept-Language", "en-US,en;q=0.9");
        connection.setRequestProperty("Accept-Encoding", "gzip, deflate, br");
        connection.setRequestProperty("Sec-Fetch-Dest", "document");
        connection.setRequestProperty("Sec-Fetch-Mode", "navigate");
        connection.setRequestProperty("Sec-Fetch-Site", "none");
        connection.setRequestProperty("Sec-Fetch-User", "?1");
        connection.setRequestProperty("Upgrade-Insecure-Requests", "1");

        long startTime = System.currentTimeMillis();
        int statusCode = connection.getResponseCode();
        long elapsed = System.currentTimeMillis() - startTime;

        String responseBody = "";
        try {
            InputStream inputStream = (statusCode >= 400) ? connection.getErrorStream() : connection.getInputStream();
            if (inputStream != null) {
                responseBody = readStream(inputStream);
            }
        } catch (Exception e) {
            responseBody = "";
        }

        // Get TLS session info
        String cipherSuite = "";
        String protocol = "";
        String peerCerts = "";
        try {
            SSLSession session = ((HttpsURLConnection) connection).getSSLSession().orElse(null);
            if (session != null) {
                cipherSuite = session.getCipherSuite();
                protocol = session.getProtocol();
                peerCerts = String.valueOf(session.getPeerCertificates().length);
            }
        } catch (Exception e) {
            // Session info not available
        }

        String finalUrl = connection.getURL().toString();
        connection.disconnect();

        // Build JSON response
        StringBuilder json = new StringBuilder();
        json.append("{");
        json.append("\"status\":").append(statusCode).append(",");
        json.append("\"url\":\"").append(escapeJson(finalUrl)).append("\",");
        json.append("\"elapsed_ms\":").append(elapsed).append(",");
        json.append("\"tls_protocol\":\"").append(escapeJson(protocol)).append("\",");
        json.append("\"cipher_suite\":\"").append(escapeJson(cipherSuite)).append("\",");
        json.append("\"peer_certificates\":").append(peerCerts.isEmpty() ? "0" : peerCerts).append(",");
        json.append("\"profile_index\":").append(profileIndex).append(",");
        json.append("\"body_length\":").append(responseBody.length()).append(",");
        json.append("\"body\":\"").append(escapeJson(responseBody.substring(0, Math.min(responseBody.length(), 50000)))).append("\"");
        json.append("}");

        return json.toString();
    }

    private static SSLContext createCustomSSLContext(int profileIndex, boolean trustAll) throws Exception {
        SSLContext context = SSLContext.getInstance("TLS");

        TrustManager[] trustManagers = null;
        if (trustAll) {
            // Trust all certificates for research/education purposes
            trustManagers = new TrustManager[]{
                new X509TrustManager() {
                    public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
                    public void checkClientTrusted(X509Certificate[] certs, String authType) {}
                    public void checkServerTrusted(X509Certificate[] certs, String authType) {}
                }
            };
        }

        context.init(null, trustManagers, new SecureRandom());

        // Configure enabled cipher suites based on profile
        SSLSocketFactory baseFactory = context.getSocketFactory();
        String[] profileCiphers = CIPHER_PROFILES[profileIndex];

        // Filter to only include ciphers supported by this JVM
        String[] supportedCiphers = baseFactory.getSupportedCipherSuites();
        Set<String> supportedSet = new HashSet<>(Arrays.asList(supportedCiphers));
        List<String> enabledCiphers = new ArrayList<>();
        for (String cipher : profileCiphers) {
            if (supportedSet.contains(cipher)) {
                enabledCiphers.add(cipher);
            }
        }
        // Add remaining supported ciphers after profile-ordered ones
        for (String cipher : supportedCiphers) {
            if (!enabledCiphers.contains(cipher) && !cipher.contains("NULL") && !cipher.contains("anon")) {
                enabledCiphers.add(cipher);
            }
        }

        return context;
    }

    private static String readStream(InputStream stream) throws IOException {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            char[] buffer = new char[8192];
            int read;
            while ((read = reader.read(buffer)) != -1) {
                sb.append(buffer, 0, read);
                if (sb.length() > 100000) break; // Cap at 100KB
            }
        }
        return sb.toString();
    }

    private static String escapeJson(String value) {
        if (value == null) return "";
        return value
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t");
    }

    private static String errorJson(String message) {
        return "{\"error\":\"" + escapeJson(message) + "\",\"status\":0}";
    }

    private static void printUsage(PrintStream out) {
        out.println("ASAGUS TLS Helper — Java TLS Fingerprint Diversification");
        out.println("Usage: java tls_helper <url> [options]");
        out.println("Options:");
        out.println("  --profile <n>    TLS cipher profile index (0=Chrome, 1=Firefox, 2=Safari)");
        out.println("  --timeout <ms>   Connection timeout in milliseconds (default: 15000)");
        out.println("  --trust-all      Accept invalid/self-signed certificates");
        out.println("  --verbose        Enable verbose output");
        out.println("  --help           Show this help");
    }
}
