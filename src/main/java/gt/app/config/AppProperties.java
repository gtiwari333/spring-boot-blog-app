package gt.app.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app-properties", ignoreUnknownFields = false)
public record AppProperties(FileStorage fileStorage) {
    public AppProperties() {
        this(null);
    }

    public record FileStorage(String uploadFolder) {
    }
}
