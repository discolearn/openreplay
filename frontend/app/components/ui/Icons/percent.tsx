/* Auto-generated, do not edit */
import React from 'react';

interface Props {
  size?: number | string;
  width?: number | string;
  height?: number | string;
  fill?: string;
}

function Percent(props: Props) {
    const { size = 14, width = size, height = size, fill = '' } = props;
    return (
      <svg viewBox="0 0 16 16" width={ `${ width }px` } height={ `${ height }px` } ><path d="M13.442 2.558a.625.625 0 0 1 0 .884l-10 10a.625.625 0 1 1-.884-.884l10-10a.625.625 0 0 1 .884 0zM4.5 6a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm0 1a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zm7 6a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm0 1a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"/></svg>
  );
}

export default Percent;
