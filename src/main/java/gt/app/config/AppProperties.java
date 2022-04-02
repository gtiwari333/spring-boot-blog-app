package gt.app.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.ConstructorBinding;

@ConfigurationProperties(prefix = "app-properties", ignoreUnknownFields = false)
public record AppProperties(FileStorage fileStorage) {
    public record FileStorage(String uploadFolder) {
    }
}
