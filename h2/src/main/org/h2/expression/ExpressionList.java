/*
 * Copyright 2004-2025 H2 Group. Multiple-Licensed under the MPL 2.0,
 * and the EPL 1.0 (https://h2database.com/html/license.html).
 * Initial Developer: H2 Group
 */
package org.h2.expression;

import org.h2.engine.SessionLocal;
import org.h2.message.DbException;
import org.h2.table.ColumnResolver;
import org.h2.table.TableFilter;
import org.h2.value.ExtTypeInfoRow;
import org.h2.value.TypeInfo;
import org.h2.value.Value;
import org.h2.value.ValueArray;
import org.h2.value.ValueRow;

/**
 * A list of expressions, as in (ID, NAME).
 * The result of this expression is a row or an array.
 */
public final class ExpressionList extends Expression {

    private final Expression[] list;
    private final boolean isArray;
    private TypeInfo type;

    public ExpressionList(Expression[] list, boolean isArray) {
        this.list = list;
        this.isArray = isArray;
    }

    @Override
    public Value getValue(SessionLocal session) {
        Value[] v = new Value[list.length];
        for (int i = 0; i < list.length; i++) {
            v[i] = list[i].getValue(session);
        }
        return isArray ? ValueArray.get((TypeInfo) type.getExtTypeInfo(), v, session) : ValueRow.get(type, v);
    }

    @Override
    public TypeInfo getType() {
        return type;
    }

    @Override
    public void mapColumns(ColumnResolver resolver, int level, int state) {
        for (Expression e : list) {
            e.mapColumns(resolver, level, state);
        }
    }

    @Override
    public Expression optimize(SessionLocal session) {
        boolean allConst = true;
        int count = list.length;
        for (int i = 0; i < count; i++) {
            Expression e = list[i].optimize(session);
            if (!e.isConstant()) {
                allConst = false;
            }
            list[i] = e;
        }
        initializeType();
        if (allConst) {
            return ValueExpression.get(getValue(session));
        }
        return this;
    }

    void initializeType() {
        type = isArray ? TypeInfo.getTypeInfo(Value.ARRAY, list.length, 0, TypeInfo.getHigherType(list))
                : TypeInfo.getTypeInfo(Value.ROW, 0, 0, new ExtTypeInfoRow(list));
    }

    @Override
    public void setEvaluatable(TableFilter tableFilter, boolean b) {
        for (Expression e : list) {
            e.setEvaluatable(tableFilter, b);
        }
    }

    @Override
    public StringBuilder getUnenclosedSQL(StringBuilder builder, int sqlFlags) {
        return isArray //
                ? writeExpressions(builder.append("ARRAY ["), list, sqlFlags).append(']')
                : writeExpressions(builder.append("ROW ("), list, sqlFlags).append(')');
    }

    @Override
    public void updateAggregate(SessionLocal session, int stage) {
        for (Expression e : list) {
            e.updateAggregate(session, stage);
        }
    }

    @Override
    public boolean isEverything(ExpressionVisitor visitor) {
        for (Expression e : list) {
            if (!e.isEverything(visitor)) {
                return false;
            }
        }
        return true;
    }

    @Override
    public int getCost() {
        int cost = 1;
        for (Expression e : list) {
            cost += e.getCost();
        }
        return cost;
    }

    @Override
    public TypeInfo getTypeIfStaticallyKnown(SessionLocal session) {
        int count = list.length;
        TypeInfo[] types = new TypeInfo[count];
        for (int i = 0; i < count; i++) {
            TypeInfo t = list[i].getTypeIfStaticallyKnown(session);
            if (t == null) {
                return null;
            }
            types[i] = t;
        }
        return isArray ? TypeInfo.getTypeInfo(Value.ARRAY, list.length, 0, TypeInfo.getHigherType(types))
                : TypeInfo.getTypeInfo(Value.ROW, 0, 0, new ExtTypeInfoRow(types));
    }

    @Override
    public boolean isConstant() {
        for (Expression e : list) {
            if (!e.isConstant()) {
                return false;
            }
        }
        return true;
    }

    @Override
    public int getSubexpressionCount() {
        return list.length;
    }

    @Override
    public Expression getSubexpression(int index) {
        return list[index];
    }

    public boolean isArray() {
        return isArray;
    }

    /**
     * Creates a copy of this expression list but the new instance will contain the subexpressions according to
     * {@code newOrder}.<br />
     * E.g.: ROW (?1, ?2).cloneWithOrder([1, 0]) returns ROW (?2, ?1)
     * @param newOrder array of indexes to create the new subexpression array
     */
    public ExpressionList cloneWithOrder(int[] newOrder) {
        int length = list.length;
        if (newOrder.length != list.length) {
            throw DbException.getInternalError("Length of the new orders is different than list size.");
        }

        Expression[] newList = new Expression[length];
        for (int i = 0; i < length; i++) {
            newList[i] = list[newOrder[i]];
        }

        ExpressionList clone = new ExpressionList(newList, isArray);
        clone.initializeType();
        return clone;
    }

}
