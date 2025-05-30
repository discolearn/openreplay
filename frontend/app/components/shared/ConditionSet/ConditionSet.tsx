import React from 'react';
import { Icon, Input } from 'UI';
import cn from 'classnames';
import { FilterList, EventsList } from 'Shared/Filters/FilterList';
import { observer } from 'mobx-react-lite';
import { Typography } from 'antd';
import { BranchesOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

interface Props {
  set: number;
  removeCondition: (ind: number) => void;
  index: number;
  readonly?: boolean;
  onAddFilter: (filter: Record<string, any>) => void;
  conditions: any;
  bottomLine1: string;
  bottomLine2: string;
  onPercentChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  excludeFilterKeys?: string[];
  onUpdateFilter: (filterIndex: number, filter: any) => void;
  onRemoveFilter: (filterIndex: number) => void;
  onChangeEventsOrder: (_: any, { name, value }: any) => void;
  isConditional?: boolean;
  changeName: (name: string) => void;
  isMobile?: boolean;
}

function ConditionSetComponent({
  removeCondition,
  index,
  set,
  readonly,
  onAddFilter,
  bottomLine1,
  bottomLine2,
  onPercentChange,
  excludeFilterKeys,
  conditions,
  onUpdateFilter,
  onRemoveFilter,
  onChangeEventsOrder,
  isConditional,
  isMobile,
  changeName,
}: Props) {
  const { t } = useTranslation();
  return (
    <div className="border bg-white rounded">
      <div className="flex items-center border-b px-4 py-2 gap-2">
        {conditions.name ? (
          <div className="flex gap-2">
            <BranchesOutlined rotate={90} />
            <Typography.Text
              className="underline decoration-dashed decoration-black cursor-pointer"
              editable={{
                onChange: changeName,
                triggerType: ['icon', 'text'],
                maxLength: 20,
              }}
            >
              {conditions.name}
            </Typography.Text>
          </div>
        ) : (
          <>
            <div>{t('Condition')}</div>
            <div className="p-2 rounded bg-gray-lightest">
              {t('Set')}
              {set}
            </div>
          </>
        )}
        {readonly ? null : (
          <div
            className={cn(
              'p-2 px-4 cursor-pointer rounded ml-auto',
              'hover:bg-teal-light',
            )}
            onClick={() => removeCondition(index)}
          >
            <Icon name="trash" color="main" />
          </div>
        )}
      </div>
      <div className="p-2">
        <div className={conditions.filter.filters.length > 0 ? 'p-2 mb-2' : ''}>
          <EventsList
            filter={conditions.filter}
            onUpdateFilter={onUpdateFilter}
            onRemoveFilter={onRemoveFilter}
            onChangeEventsOrder={onChangeEventsOrder}
            hideEventsOrder
            onAddFilter={onAddFilter}
            excludeFilterKeys={excludeFilterKeys}
            readonly={readonly}
            isConditional={isConditional}
            borderless
          />
          <FilterList
            filter={conditions.filter}
            onUpdateFilter={onUpdateFilter}
            onRemoveFilter={onRemoveFilter}
            onChangeEventsOrder={onChangeEventsOrder}
            hideEventsOrder
            onAddFilter={onAddFilter}
            excludeFilterKeys={excludeFilterKeys}
            readonly={readonly}
            isConditional={isConditional}
            borderless
          />
          {readonly && !conditions.filter?.filters?.length ? (
            <div className="p-2">{t('No conditions')}</div>
          ) : null}
        </div>
      </div>
      <div className="px-4 py-2 flex items-center gap-2 border-t">
        <span>{bottomLine1}</span>
        {readonly ? (
          <div className="font-semibold">{conditions.rolloutPercentage}%</div>
        ) : (
          <Input
            type="text"
            width={60}
            value={conditions.rolloutPercentage}
            onChange={onPercentChange}
            leadingButton={<div className="p-2 text-disabled-text">%</div>}
          />
        )}

        <span>{bottomLine2}</span>
      </div>
    </div>
  );
}

export default observer(ConditionSetComponent);
