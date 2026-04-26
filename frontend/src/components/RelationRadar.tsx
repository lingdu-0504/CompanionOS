import React from 'react';
import type { CompanionState } from '../types';
import './RelationRadar.css';

interface Props {
  companion: CompanionState;
}

const DIMENSIONS = [
  { key: 'affection', label: '好感', color: '#ff6b9d' },
  { key: 'trust', label: '信任', color: '#64ffda' },
  { key: 'intimacy', label: '亲密', color: '#c792ea' },
  { key: 'comfort', label: '舒适', color: '#82aaff' },
  { key: 'respect', label: '尊重', color: '#ffd700' },
] as const;

export const RelationRadar: React.FC<Props> = ({ companion }) => {
  return (
    <div className="relation-radar">
      <div className="radar-title">关系维度</div>
      <div className="radar-bars">
        {DIMENSIONS.map((dim) => (
          <div key={dim.key} className="radar-row">
            <span className="radar-label">{dim.label}</span>
            <div className="radar-bar-bg">
              <div
                className="radar-bar-fill"
                style={{
                  width: `${companion[dim.key]}%`,
                  background: dim.color,
                }}
              />
            </div>
            <span className="radar-value">{Math.round(companion[dim.key])}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
