package gt.app.config;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.hibernate.boot.Metadata;
import org.hibernate.mapping.*;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.stereotype.Component;

import jakarta.persistence.EntityManager;
import java.util.Iterator;

//@Component disabled since class is not actually used and was added for my blog
@RequiredArgsConstructor
@Slf4j
public class DBMetadataReader implements InitializingBean {
    final EntityManager em;

    @Override
    public void afterPropertiesSet() {

        Metadata metadata = MetadataExtractorIntegrator.INSTANCE.getMetadata();

        //Collection tables
        for (Collection c : metadata.getCollectionBindings()) {
            log.info("Collection table: {}", c.getCollectionTable().getQualifiedTableName());
            for (Column property : c.getCollectionTable().getColumns()) {
                log.info("   {}   {} ", property.getName(), property.getSqlType());
            }
        }

        //all entities
        for (PersistentClass pc : metadata.getEntityBindings()) {
            Table table = pc.getTable();

            log.info("Entity: {} - {}", pc.getClassName(), table.getName());

            KeyValue identifier = pc.getIdentifier();

            //PK
            for (Column column : identifier.getColumns()) {
                log.info("    PK: {}  {}", column.getName(), column.getSqlType());
            }

            //property/columns
            for (Property property : pc.getProperties()) {
                for (Column column : property.getColumns()) {
                    log.info("    {}  {}", column.getName(), column.getSqlType());
                }
            }
        }
    }
}
