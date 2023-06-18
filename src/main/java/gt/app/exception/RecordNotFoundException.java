package gt.app.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(value = HttpStatus.NOT_FOUND)
public class RecordNotFoundException extends RuntimeException {

    public RecordNotFoundException(String description) {
        super(description);
    }

    public RecordNotFoundException(String requestedObjectName, String requestedByField, Object requestedByParam) {
        super("%s not found with %s = '%s'".formatted(requestedObjectName, requestedByField, requestedByParam));
    }
}
