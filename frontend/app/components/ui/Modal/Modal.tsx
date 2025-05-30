import React, { useEffect } from 'react';
import cn from 'classnames';

interface Props {
  children: React.ReactNode;
  open?: boolean;
  size?: 'tiny' | 'small' | 'large' | 'fullscreen' | 'xlarge';
  onClose?: () => void;
}
function Modal(props: Props) {
  const { children, open = false, size = 'small' } = props;

  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.body.style.overflow = 'auto';
    };
  }, [open]);

  const style: any = {};
  switch (size) {
    case 'tiny':
      style.width = '300px';
      break;
    case 'small':
      style.width = '420px';
      break;
    case 'large':
      style.width = '700px';
      break;
    case 'xlarge':
      style.width = '846px';
      break;
    case 'fullscreen':
      style.width = '100%';
      break;
  }

  const handleClose = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      props.onClose && props.onClose();
    }
  };

  return open ? (
    <div
      className="fixed inset-0 flex items-center justify-center box-shadow animate-fade-in"
      style={{ zIndex: '9999', backgroundColor: 'rgba(0, 0, 0, 0.2)' }}
      onClick={handleClose}
    >
      <div
        className="absolute z-10 bg-white rounded-lg shadow-sm"
        style={style}
      >
        {children}
      </div>
    </div>
  ) : null;
}

interface ModalContentProps {
  children: React.ReactNode;
  className?: string;
}

function ModalContent(props: ModalContentProps) {
  const { children, className } = props;
  return (
    <div
      className={cn('p-5', className)}
      style={{ maxHeight: 'calc(100vh - 100px)' }}
    >
      {children}
    </div>
  );
}

interface ModalHeaderProps {
  children: React.ReactNode;
  className?: string;
}
function ModalHeader(props: ModalHeaderProps) {
  const { children, className = '' } = props;
  return (
    <div
      className={cn(
        'px-5 py-3 flex items-center justify-between text-2xl border-b',
        className,
      )}
    >
      {children}
    </div>
  );
}

interface ModalFooterProps {
  children: React.ReactNode;
  className?: string;
}
function ModalFooter(props: ModalFooterProps) {
  const { children, className = '' } = props;
  return (
    <div className={cn('p-5 flex items-center', className)}>{children}</div>
  );
}

Modal.Header = ModalHeader;
Modal.Footer = ModalFooter;
Modal.Content = ModalContent;

export default Modal;
