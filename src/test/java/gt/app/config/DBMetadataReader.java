package gt.app.config;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.hibernate.boot.Metadata;
import org.hibernate.mapping.*;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.stereotype.Component;

import javax.persistence.EntityManager;
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
            for (Iterator<Column> it = c.getCollectionTable().getColumnIterator();
                 it.hasNext(); ) {
                Column property = it.next();
                log.info("   {}   {} ", property.getName(), property.getSqlType());
            }
        }

        //all entities
        for (PersistentClass pc : metadata.getEntityBindings()) {
            Table table = pc.getTable();

            log.info("Entity: {} - {}", pc.getClassName(), table.getName());

            KeyValue identifier = pc.getIdentifier();

            //PK
            for (Iterator<Selectable> it = identifier.getColumnIterator();
                 it.hasNext(); ) {
                Column column = (Column) it.next();
                log.info("    PK: {}  {}", column.getName(), column.getSqlType());
            }

            //property/columns
            for (Iterator it = pc.getPropertyIterator();
                 it.hasNext(); ) {
                Property property = (Property) it.next();

                for (Iterator columnIterator = property.getColumnIterator();
                     columnIterator.hasNext(); ) {
                    Column column = (Column) columnIterator.next();
                    log.info("    {}  {}", column.getName(), column.getSqlType());
                }
            }
        }
    }
}
