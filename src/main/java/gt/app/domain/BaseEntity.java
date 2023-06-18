package gt.app.domain;

import lombok.Data;

import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.MappedSuperclass;

@Data
@MappedSuperclass
@SuppressWarnings("DirectReturn") //getting [ERROR]      java.lang.IllegalArgumentException: Replacement{range=[165..170), replaceWith=} conflicts with existing replacement Replacement{range=[165..170), replaceWith=return @Data;}
public abstract class BaseEntity {

    @Id
    @GeneratedValue
    protected Long id;
}
