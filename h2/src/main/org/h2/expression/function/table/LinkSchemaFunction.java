/*
 * Copyright 2004-2020 H2 Group. Multiple-Licensed under the MPL 2.0,
 * and the EPL 1.0 (https://h2database.com/html/license.html).
 * Initial Developer: H2 Group
 */
package org.h2.expression.function.table;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

import org.h2.api.ErrorCode;
import org.h2.engine.SessionLocal;
import org.h2.expression.Expression;
import org.h2.expression.ExpressionVisitor;
import org.h2.expression.function.FunctionCall;
import org.h2.expression.function.FunctionN;
import org.h2.message.DbException;
import org.h2.result.SimpleResult;
import org.h2.util.JdbcUtils;
import org.h2.util.StringUtils;
import org.h2.value.TypeInfo;
import org.h2.value.Value;
import org.h2.value.ValueResultSet;
import org.h2.value.ValueVarchar;

/**
 * A LINK_SCHEMA function.
 */
public final class LinkSchemaFunction extends FunctionN implements FunctionCall {

    public LinkSchemaFunction() {
        super(new Expression[6]);
    }

    @Override
    public Value getValue(SessionLocal session) {
        session.getUser().checkAdmin();
        String targetSchema = getValue(session, 0);
        String driver = getValue(session, 1);
        String url = getValue(session, 2);
        String user = getValue(session, 3);
        String password = getValue(session, 4);
        String sourceSchema = getValue(session, 5);
        if (targetSchema == null || driver == null || url == null || user == null || password == null
                || sourceSchema == null) {
            return getValueForColumnList(session, null);
        }
        Connection conn = session.createConnection(false);
        Connection c2 = null;
        Statement stat = null;
        ResultSet rs = null;
        SimpleResult result = new SimpleResult();
        result.addColumn("TABLE_NAME", TypeInfo.TYPE_VARCHAR);
        try {
            c2 = JdbcUtils.getConnection(driver, url, user, password);
            stat = conn.createStatement();
            stat.execute(StringUtils.quoteIdentifier(new StringBuilder("CREATE SCHEMA IF NOT EXISTS "), targetSchema)
                    .toString());
            // Workaround for PostgreSQL to avoid index names
            if (url.startsWith("jdbc:postgresql:")) {
                rs = c2.getMetaData().getTables(null, sourceSchema, null,
                        new String[] { "TABLE", "LINKED TABLE", "VIEW", "EXTERNAL" });
            } else {
                rs = c2.getMetaData().getTables(null, sourceSchema, null, null);
            }
            while (rs.next()) {
                String table = rs.getString("TABLE_NAME");
                StringBuilder buff = new StringBuilder();
                buff.append("DROP TABLE IF EXISTS ");
                StringUtils.quoteIdentifier(buff, targetSchema).append('.');
                StringUtils.quoteIdentifier(buff, table);
                stat.execute(buff.toString());
                buff.setLength(0);
                buff.append("CREATE LINKED TABLE ");
                StringUtils.quoteIdentifier(buff, targetSchema).append('.');
                StringUtils.quoteIdentifier(buff, table).append('(');
                StringUtils.quoteStringSQL(buff, driver).append(", ");
                StringUtils.quoteStringSQL(buff, url).append(", ");
                StringUtils.quoteStringSQL(buff, user).append(", ");
                StringUtils.quoteStringSQL(buff, password).append(", ");
                StringUtils.quoteStringSQL(buff, sourceSchema).append(", ");
                StringUtils.quoteStringSQL(buff, table).append(')');
                stat.execute(buff.toString());
                result.addRow(ValueVarchar.get(table, session));
            }
        } catch (SQLException e) {
            result.close();
            throw DbException.convert(e);
        } finally {
            JdbcUtils.closeSilently(rs);
            JdbcUtils.closeSilently(c2);
            JdbcUtils.closeSilently(stat);
        }
        return ValueResultSet.get(result);
    }

    private String getValue(SessionLocal session, int index) {
        return args[index].getValue(session).getString();
    }

    @Override
    public Expression optimize(SessionLocal session) {
        optimizeArguments(session, false);
        int len = args.length;
        if (len != 6) {
            throw DbException.get(ErrorCode.INVALID_PARAMETER_COUNT_2, getName(), "6");
        }
        type = TypeInfo.TYPE_RESULT_SET;
        return this;
    }

    @Override
    public ValueResultSet getValueForColumnList(SessionLocal session, Expression[] nullArgs) {
        SimpleResult result = new SimpleResult();
        result.addColumn("TABLE_NAME", TypeInfo.TYPE_VARCHAR);
        return ValueResultSet.get(result);
    }

    @Override
    public Expression[] getExpressionColumns(SessionLocal session) {
        return getExpressionColumns(session, getValueForColumnList(session, null).getResult());
    }

    @Override
    public String getName() {
        return "LINK_SCHEMA";
    }

    @Override
    public Expression[] getArgs() {
        return args;
    }

    @Override
    public int getValueType() {
        return Value.RESULT_SET;
    }

    @Override
    public boolean isDeterministic() {
        return false;
    }

    @Override
    public boolean isEverything(ExpressionVisitor visitor) {
        return isEverythingNonDeterministic(visitor);
    }

}