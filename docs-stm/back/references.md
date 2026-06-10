# 参考文献

> 本书在分析和撰写过程中参考的官方文档、学术论文和技术资料。分类整理如下。

---

## H2 官方文档

H2 Database 官方文档是本书最主要的参考来源。以下文档随 H2 源码提供，位于 `h2/src/docsrc/html/` 目录：

1. **《Architecture》** (`architecture.html`)
   H2 整体架构的分层描述，包含 JDBC 驱动、引擎层、存储层等核心组件的设计说明。

2. **《MVStore》** (`mvstore.html`)
   MVStore 存储引擎的完整文档，包括文件格式（file header/chunk/page 三级布局）、事务机制、缓存策略和性能调优。

3. **《Advanced》** (`advanced.html`)
   高级特性文档，涵盖事务隔离级别、MVCC 行为、ACID 保证、SQL 注入防护、远程访问安全、锁超时等。

4. **《Features》** (`features.html`)
   特性清单，包含连接模式、SQL 支持、集群模式和功能完整特性列表。

5. **《Performance》** (`performance.html`)
   性能基准测试结果（H2 vs HSQLDB/Derby/PostgreSQL/MySQL），以及数据库性能调优指南和内置分析器使用说明。

6. **《Security》** (`security.html`)
   安全特性文档，包括存储加密、传输加密、访问控制和类加载限制。

7. **《Tutorial》** (`tutorial.html`)
   H2 使用教程，包含命令行工具说明、嵌入式和客户端-服务器模式的快速入门指南。

## 学术论文

8. **Bayer, R. & McCreight, E. (1972).** *Organization and Maintenance of Large Ordered Indexes.* Acta Informatica, 1(3), 173-189.
   B-Tree 的原始论文，提出了平衡多路查找树的数据结构和维护算法。

9. **Jiang, S. & Zhang, X. (2002).** *LIRS: An Efficient Low Inter-reference Recency Set Replacement Policy to Improve Buffer Cache Performance.* ACM SIGMETRICS.
   LIRS 缓存替换算法的原始论文，提出了基于 IRR（Inter-Reference Recency）的缓存替换策略。

10. **Guttman, A. (1984).** *R-Trees: A Dynamic Index Structure for Spatial Searching.* ACM SIGMOD.
    R-Tree 空间索引的原始论文。

11. **Bernstein, P. A., Hadzilacos, V. & Goodman, N. (1987).** *Concurrency Control and Recovery in Database Systems.* Addison-Wesley.
    数据库并发控制和恢复的经典参考书，涉及 MVCC、锁协议和恢复算法。

12. **Gray, J. & Reuter, A. (1993).** *Transaction Processing: Concepts and Techniques.* Morgan Kaufmann.
    事务处理的权威著作，涵盖 ACID 特性、隔离级别和恢复机制的完整理论。

13. **Codd, E. F. (1970).** *A Relational Model of Data for Large Shared Data Banks.* Communications of the ACM, 13(6), 377-387.
    关系模型的奠基性论文。

## 技术参考

14. **Oracle Corporation. (2024).** *Java Platform, Standard Edition API Specification.*
    Java 标准库 API 文档，涉及 `java.nio.channels.FileChannel`、`java.sql` 等核心接口。

15. **ISO/IEC 9075:2023.** *Information technology — Database languages — SQL.*
    SQL 标准，H2 实现了 SQL'99+ 的大部分特性。

## 对比数据库文档

16. **SQLite Consortium. (2024).** *SQLite Documentation.* https://www.sqlite.org/docs.html
17. **Apache Software Foundation. (2024).** *Apache Derby Documentation.* https://db.apache.org/derby/docs/
18. **The HSQL Development Group. (2024).** *HSQLDB Documentation.* https://hsqldb.org/doc/
19. **PostgreSQL Global Development Group. (2024).** *PostgreSQL Documentation.* https://www.postgresql.org/docs/
20. **Oracle Corporation. (2024).** *MySQL Documentation.* https://dev.mysql.com/doc/

---

*共收录 20 条参考文献。编号采用 [作者, 年份] 格式标识学术论文，H2 官方文档以《标题》格式引用，技术参考和对比数据库文档以组织名和年份标识。*